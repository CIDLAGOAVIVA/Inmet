#!/bin/env python

import os
import sys
import time
import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from datetime import datetime, timedelta
from webdriver_manager.chrome import ChromeDriverManager

# Função principal para processar os dados de uma estação
def process_station(estacao, data_inicial, data_final, metadados):
    # Carrega os dados existentes do CSV para verificar a última data por estação, se necessário
    if os.path.exists(csv_filename):
        df_existing = pd.read_csv(csv_filename, delimiter=';', parse_dates=['data'], dayfirst=True)
        df_existing['data'] = pd.to_datetime(df_existing['data'], errors='coerce', format='%d/%m/%Y %H:%M:%S')
        df_existing = df_existing[df_existing['station'] == estacao]
        if not df_existing.empty:
            last_date = df_existing['data'].max()
            if not data_inicial:
                data_inicial = last_date + timedelta(days=1)
        else:
            if not data_inicial:
                data_inicial = datetime.strptime("01/06/2024", "%d/%m/%Y")
    else:
        if not data_inicial:
            data_inicial = datetime.strptime("01/06/2024", "%d/%m/%Y")

    # Variáveis para metadados da estação
    # metadados = "G:/Meu Drive/CID/Raspagem/chuvas/CatalogoEstaçõesAutomáticas.csv"

    # Carrega o catálogo de estações com o delimitador correto
    stations_df = pd.read_csv(metadados, header=None, delimiter=';')

    # Define as colunas com base na descrição
    station_code_col = 7  # Coluna 8 (índice 7)
    latitude_col = 3  # Coluna 4 (índice 3)
    longitude_col = 4  # Coluna 5 (índice 4)
    altitude_col = 5  # Coluna 6 (índice 5)

    # Função para obter metadados da estação
    def get_station_metadata(station_code, stations_df):
        station_data = stations_df[stations_df[station_code_col] == station_code]
        if not station_data.empty:
            latitude = float(station_data.iloc[0, latitude_col].replace(',', '.'))
            longitude = float(station_data.iloc[0, longitude_col].replace(',', '.'))
            altitude = float(station_data.iloc[0, altitude_col].replace(',', '.'))
            return latitude, longitude, altitude
        else:
            raise ValueError(f"Código da estação {station_code} não encontrado no catálogo.")

    # Obtém latitude, longitude e altitude da estação
    latitude, longitude, altitude = get_station_metadata(estacao, stations_df)

    # Constrói a URL
    url = f"https://tempo.inmet.gov.br/TabelaEstacoes/{estacao}"
    try:
        driver.get(url)
        print(f"Página carregada com sucesso: {url}")
    except Exception as e:
        print(f"Erro ao carregar a página para a estação {estacao}: ", e)
        return

    # Aguarda o carregamento da página
    wait = WebDriverWait(driver, 30)

    # Interage com a página
    try:
        menu_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.left.menu i.bars.icon.header-icon")))
        driver.execute_script("arguments[0].click();", menu_button)
        time.sleep(2)

        
        data_inicial_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@type='date']")))
        data_inicial_input.clear()
        data_inicial_input.send_keys(data_inicial.strftime("%d/%m/%Y"))
        time.sleep(1)
        data_final_input = wait.until(EC.element_to_be_clickable((By.XPATH, "(//input[@type='date'])[2]")))
        data_final_input.clear()
        data_final_input.send_keys(data_final.strftime("%d/%m/%Y"))
        time.sleep(1)
        gerar_tabela_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Gerar Tabela')]")))
        driver.execute_script("arguments[0].click();", gerar_tabela_button)
        time.sleep(10)
    except Exception as e:
        print(f"Erro ao interagir com a página para a estação {estacao}: ", e)
        return

    # Extrai os dados da tabela
    try:
        table = wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        print("Achou tabela")
        rows = table.find_elements(By.TAG_NAME, "tr")
        print(f"{len(rows)} linhas")
        data = []
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            cols = [ele.text.strip() for ele in cols]
            if any(cols):  # Filtra linhas vazias
                data.append([ele for ele in cols if ele])
            #    print("Linha com coisa")
            #else:
            #    print("Linha VAZIA")
    except Exception as e:
        print(f"Erro ao extrair dados da tabela para a estação {estacao}: ", e)
        return

    # Salva os dados
    try:
        if data:
            df = pd.DataFrame(data)
            df.columns = [
                'data', 'hora', 'temperatura_media', 'temperatura_maxima', 'temperatura_minima',
                'umidade_media', 'umidade_maxima', 'umidade_minima', 'pto_orvalho_medio', 
                'pto_orvalho_maximo', 'pto_orvalho_minimo', 'pressao_instantanea', 'pressao_maxima', 
                'pressao_minima', 'vento_velocidade', 'vento_direcao', 'vento_rajada', 'radiacao', 
                'chuva'
            ]
            
            # Converte colunas para numérico após substituir vírgulas por pontos
            for col in df.columns[2:]:
                df[col] = df[col].str.replace(',', '.').astype(float)

            # 1. Renomeia 'temperatura_media' para 'temperatura_bulbo_seco'
            df.rename(columns={'temperatura_media': 'temperatura_bulbo_seco'}, inplace=True)

            # 2. Cria 'temperatura_media' como a média de 'temperatura_maxima' e 'temperatura_minima'
            df['temperatura_media'] = (df['temperatura_maxima'] + df['temperatura_minima']) / 2
            
            # 3. Recalcula 'pto_orvalho_medio' como a média de 'pto_orvalho_maximo' e 'pto_orvalho_minimo'
            df['pto_orvalho_medio'] = (df['pto_orvalho_maximo'] + df['pto_orvalho_minimo']) / 2

            # Formata as colunas de data e hora
            df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y', dayfirst=True)
            df['hora'] = df['hora'].apply(lambda x: f"{x[:2]}:{x[2:]}" if len(x) == 4 else x)
            
            # Cria a coluna 'data_hora' combinando 'data' e 'hora'
            df['data_hora'] = pd.to_datetime(df['data'].astype(str) + ' ' + df['hora'], format='%Y-%m-%d %H:%M')

            # Padroniza a coluna 'data' para incluir o horário 00:00:00 quando não houver horário
            df['data'] = df['data_hora'].apply(lambda x: x.replace(hour=0, minute=0, second=0))

            # Garante que cada dia tenha pelo menos 20 registros horários, caso contrário, define os registros para NaN
            df_daily_count = df.groupby('data').size()
            invalid_dates = df_daily_count[df_daily_count < 20].index
            df.loc[df['data'].isin(invalid_dates), df.columns] = np.nan
            
            # Verifica se as datas de início e fim têm 24 registros horários
            df['data'] = pd.to_datetime(df['data'], dayfirst=True)  # Garante que a coluna de data seja datetime

            # Ajusta o horário com base na longitude
            if longitude > -37.5:
                df['data_hora'] = df['data_hora'] - pd.Timedelta(hours=2)
            elif longitude > -52.5:
                df['data_hora'] = df['data_hora'] - pd.Timedelta(hours=3)
            elif longitude > -67.5:
                df['data_hora'] = df['data_hora'] - pd.Timedelta(hours=4)
            elif longitude > -82.5:
                df['data_hora'] = df['data_hora'] - pd.Timedelta(hours=5)

            # Reextrai a data e hora ajustadas
            df['data'] = df['data_hora'].dt.date
            df['hora'] = df['data_hora'].dt.hour

            # Agrupa por data para valores diários
            df_daily = df.groupby('data').agg({
                'temperatura_bulbo_seco': 'mean',  # Média diária da coluna renomeada
                'temperatura_media': 'mean',       # Média diária da nova 'temperatura_media'
                'temperatura_minima': 'min',
                'temperatura_maxima': 'max',
                'umidade_media': 'mean',
                'umidade_minima': 'min',
                'umidade_maxima': 'max',
                'pto_orvalho_medio': 'mean',       # Média diária da recalculada 'pto_orvalho_medio'
                'pressao_instantanea': 'mean',
                'vento_velocidade': 'mean',
                'vento_rajada': 'max',
                'vento_direcao': 'mean',
                'radiacao': 'sum',
                'chuva': 'sum'
            }).reset_index()

            # Converte 'data_inicial' e 'data_final' para date para comparação
            data_inicial_date = data_inicial.date()
            data_final_date = data_final.date()

            # Filtra os dados para manter apenas os registros dentro do intervalo de datas
            df_daily = df_daily[(df_daily['data'] >= data_inicial_date) & (df_daily['data'] <= data_final_date)]

            # Calcula a velocidade do vento a 2 metros de altura (u2)
            df_daily['vento_u2'] = (4.868 / (np.log(67.75 * 10 - 5.42))) * df_daily['vento_velocidade']

            # Cálculos de radiação solar
            julian_day = df_daily['data'].apply(lambda x: x.timetuple().tm_yday)
            latitude_rad = np.deg2rad(latitude)

            # Dr e Declinação Solar
            df_daily['dr'] = 1 + 0.033 * np.cos((2 * np.pi / 365) * julian_day)
            df_daily['declinacao_solar'] = 0.409 * np.sin((2 * np.pi / 365) * julian_day - 1.39)

            # Ângulo da hora do pôr do sol
            df_daily['angulo_hora_por_sol'] = np.arccos(-np.tan(latitude_rad) * np.tan(df_daily['declinacao_solar']))

            # Radiação solar extraterrestre (Ra)
            df_daily['ra'] = (24 * 60 / np.pi) * 0.082 * df_daily['dr'] * (
                df_daily['angulo_hora_por_sol'] * np.sin(latitude_rad) * np.sin(df_daily['declinacao_solar']) +
                np.cos(latitude_rad) * np.cos(df_daily['declinacao_solar']) * np.sin(df_daily['angulo_hora_por_sol'])
            )

            # Adiciona metadados da estação ao DataFrame
            df_daily['station'] = estacao
            df_daily['latitude'] = latitude
            df_daily['longitude'] = longitude
            df_daily['altitude'] = altitude

            # Converte colunas numéricas para strings com vírgula como separador decimal
            for col in df_daily.select_dtypes(include=[np.number]).columns:
                df_daily[col] = df_daily[col].apply(lambda x: f"{x:.6f}".replace('.', ','))

            # Formata a coluna 'data' para o formato dd/mm/aaaa com hora 00:00:00
            df_daily['data'] = df_daily['data'].apply(lambda x: x.strftime('%d/%m/%Y %H:%M:%S'))

            # Anexa os novos dados ao CSV existente
            if os.path.exists(csv_filename):
                df_existing = pd.read_csv(csv_filename, delimiter=';', parse_dates=['data'], dayfirst=True)
                df_combined = pd.concat([df_existing, df_daily])
                df_combined.to_csv(csv_filename, index=False, sep=';', decimal=',')
            else:
                df_daily.to_csv(csv_filename, index=False, sep=';', decimal=',')

            print(f"Dados da estação {estacao} salvos com sucesso em '{csv_filename}'")
        else:
            print(f"Nenhum dado disponível para salvar para a estação {estacao}")
    except Exception as e:
        print(f"Erro ao salvar os dados para a estação {estacao}: ", e)

if __name__ == '__main__':
    headless = False

    scriptdir = os.path.dirname(sys.argv[0])
    metadados = os.path.join(scriptdir, "CatalogoEstacoesAutomaticas.csv")
    args = sys.argv[1:]
    try:
        if args[0] == "-h":
            headless = True
            args = args[1:]
    except:
        pass
    try:
        estacao = args[0]
        data_inicial_str = args[1]
        data_final_str = args[2]
    except:
        # Solicita os inputs do usuário
        estacao = input("Digite o código da estação ou deixe em branco para usar todas as estações do arquivo existente: ")
        data_inicial_str = input("Digite a data inicial (dd/mm/aaaa) ou deixe em branco para usar a última data disponível: ")
        data_final_str = input("Digite a data final (dd/mm/aaaa) ou deixe em branco para usar a data atual: ")

    # Define o nome do arquivo CSV de saída
    csv_filename = "final_inmet_data.csv"

    # Converte as strings de data para objetos datetime
    data_inicial = datetime.strptime(data_inicial_str, "%d/%m/%Y") if data_inicial_str else None
    data_final = datetime.strptime(data_final_str, "%d/%m/%Y") if data_final_str else datetime.today()

    # Tenta inicializar o WebDriver com os caminhos definidos
    try:
        if headless:
            options = Options()
            options.add_argument("--headless")
            driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options = options)
        else:
            driver = webdriver.Chrome()
    except FileNotFoundError as e:
        print(e)
        exit(1)

    # Verifica se está em um ambiente virtual
    if 'VIRTUAL_ENV' in os.environ:
        print("Está em um ambiente virtual")
    else:
        print("Não está em um ambiente virtual")

    # Verifica se uma estação foi especificada
    if estacao:
        # Processa apenas a estação especificada
        process_station(estacao, data_inicial, data_final, metadados)
    else:
        # Carrega o arquivo CSV existente para verificar as estações já processadas
        if os.path.exists(csv_filename):
            df_existing = pd.read_csv(csv_filename, delimiter=';', parse_dates=['data'], dayfirst=True)
            df_existing['data'] = pd.to_datetime(df_existing['data'], errors='coerce', format='%d/%m/%Y %H:%M:%S')
            estações_existentes = df_existing['station'].unique()

            # Processa cada estação existente no arquivo CSV
            for estacao in estações_existentes:
                # Definir as datas inicial e final para cada estação individualmente
                process_station(estacao, None, data_final, metadados)
        else:
            print("Nenhuma estação especificada e nenhum arquivo CSV existente encontrado.")
            exit(1)

    # Finaliza o WebDriver
    driver.quit()

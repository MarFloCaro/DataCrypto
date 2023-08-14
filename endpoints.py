import requests
import pandas as pd
from time import sleep
from dateutil import parser
from datetime import datetime
from dateutil.relativedelta import relativedelta


# CoinMarketCap headers
HEADERS = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': '09987570-1ba1-482f-8758-e2056f73b7dd',
  }

# Session Objects para las llamadas a los endpoints de CoinMarketCap
session = requests.Session()
session.headers.update(HEADERS)


# CoinGecko

def get_coins_list():
    """ Llamada al endpoint que lista las monedas disponibles en CoinGecko """

    # Hacer llamada a la URL de la API
    base_url = "https://api.coingecko.com/api/v3/coins/list"
    response = requests.get(base_url)

    # Respuesta exitosa
    if response.status_code == 200:
        # Conversión a diccionario de Python o lista
        data = response.json()

        # Retornamos un dataframe
        return pd.DataFrame(data)
    else:
         return f"El llamado al endpoint falló con código de error {response.status_code}"
    

def get_coins_markets(crypto_ids):
    """ Llamada al endpoint que retorna datos de mercado de un listado de monedas provisto """

    # Base de la URL
    base_url = "https://api.coingecko.com/api/v3/coins/markets"
    # Parámetros
    params = {
        "vs_currency": "USD",
        "ids": ",".join(crypto_ids),
        "order": "market_cap_desc",
        "per_page": "100",
        "page": "1",
        "sparkline": "false",
        "locale": "en"
    }

    # Llamada al endpoint
    response = requests.get(base_url, params=params)

    # Llamada Exitosa
    if response.status_code == 200:
        data = response.json()

        # Guardamos en Dataframe
        df = pd.DataFrame(data)

        # Convertimos las columnas de fecha a datetime64[ns]
        date_columns = ['ath_date', 'atl_date', 'last_updated']
        for col in date_columns:
            df[col] = pd.to_datetime(df[col]).dt.tz_localize(None)
        # Convertimos 'roi' a float64
        df['roi'] = df['roi'].astype(float)

        return df
    else:
        return f"El llamado al endpoint falló con código de error {response.status_code}"
    

def get_coins_id(crypto_ids):
    """ Llamado al endpoint que retorna información de las monedas, tomando su id como parámetro """

    # Base de la URL
    base_url = "https://api.coingecko.com/api/v3/coins/"

    # Inicializamos una lista para guardar las respuestas API
    coin_data = []

    for call, crypto_id in enumerate(crypto_ids):
        # Para evitar error 429
        if call > 9:
            sleep(60)
        
        # Llamado
        url = base_url + crypto_id
        response = requests.get(url)

        # Respuesta exitosa
        if response.status_code == 200:
            coin_info = response.json()
            coin_data.append(coin_info)
        else:
            return f"El llamado al endpoint de la moneda {crypto_id} falló con código de error {response.status_code}"

    # Creamos el dataframe
    df =  pd.DataFrame(coin_data)
    # Pasamos a datetime
    df['last_updated'] = pd.to_datetime(df['last_updated']).dt.tz_localize(None)

    return df


def get_coins_id_filtered(crypto_ids):
    """ Llamado al endpoint que retorna información estilo metadata de las monedas, tomando su id como parámetro 
    
    Esta versión omite localization, tickers, market data y community data
    """

    # Base de la URL
    base_url = "https://api.coingecko.com/api/v3/coins/{}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "false",
        "community_data": "false"
    }

    # Inicializamos las listas que originarán los dataframes
    coin_data = []
    developer_dicts = []


    # Loop para las llamadas
    for call, crypto_id in enumerate(crypto_ids):
        # Para evitar error 429
        if call > 9:
            sleep(60)

        url = base_url.format(crypto_id)
        response = requests.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            # Separamos developer data de la respuesta
            developer_data = data.pop('developer_data')
            # Eliminamos otras keys que no nos interesan
            to_delete = [
                'asset_platform_id',
                'platforms',
                'detail_platforms',
                'public_notice',
                'additional_notices',
                'description',
                'links',
                'image',
                'country_origin',
                'public_interest_stats',
                'status_updates',
                'contract_address',
                'tickers'
                ]
            data = {key: value for key, value  in data.items() if key not in to_delete}
            coin_data.append(data)

            # Iniciamos un dicionario para la developer data
            developer_df = dict()        
            # Usamos los datos de la respuesta para darle id, symbol y name
            developer_df['id'] = data.get('id')
            developer_df['symbol'] = data.get('symbol')
            developer_df['name'] = data.get('name')    
            # Actualizamos el diccionario con developer data 
            developer_df.update(developer_data)
            # Agregamos el diccionario a la lista de developer_dicts
            developer_dicts.append(developer_df)
        else:
             return f"El llamado al endpoint de la moneda {crypto_id} falló con código de error {response.status_code}"

    df_coins = pd.DataFrame(coin_data)
    df_coins['last_updated'] = pd.to_datetime(df_coins['last_updated']).dt.tz_localize(None)


    df_developers = pd.DataFrame(developer_dicts)
    # Dividimos la columna code additions...
    additions_deletions_series = df_developers['code_additions_deletions_4_weeks'].apply(pd.Series)
    df_developers['code_additions_4_weeks'] = additions_deletions_series['additions']
    df_developers['code_deletions_4_weeks'] = additions_deletions_series['deletions']
    df_developers.drop(columns='code_additions_deletions_4_weeks', inplace=True)
    #  Reemplazamos listas en 'last_4_weeks_commit_activity_series' con su sumatoria
    df_developers['last_4_weeks_commit_activity_sum'] = df_developers['last_4_weeks_commit_activity_series'].apply(sum)
    df_developers.drop(columns='last_4_weeks_commit_activity_series', inplace=True)


    return df_coins, df_developers
    

def get_coins_tickers(crypto_ids):
    """ Llamado al endpoint tickers, que retorna información de la moneda en distintos brokers que la operan """

    # URL base para ticker
    base_url = "https://api.coingecko.com/api/v3/coins/{}/tickers"

    # Diccionario para los dataframes
    dataframes = {}

    # Loop para recorrer la lista de IDs de monedas crypto
    for call, crypto_id in enumerate(crypto_ids):
        # Evitamos error 429
        if call > 9:
            sleep(60)

        url = base_url.format(crypto_id)
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            # Desanidamos
            tickers = data.get("tickers", [])

            ticker_data_list = []
            for ticker in tickers:
                ticker_data = {}
                for key, value in ticker.items():
                    # Columnas con fecha/hora
                    if key in ["timestamp", "last_traded_at", "last_fetch_at"]:
                        # Conversión a formato datetime
                        datetime_str = parser.parse(value).strftime('%Y-%m-%d %H:%M:%S')
                        # Ahora lo convertimos sin UTC a formato uniforme a pandas
                        ticker_data[key] = pd.to_datetime(datetime_str)
                    # Desanidamos columnas que tienen diccionarios como valor
                    elif isinstance(value, dict):
                        for inner_key, inner_value in value.items():
                            ticker_data[f"{key}_{inner_key}"] = inner_value
                    else:
                        ticker_data[key] = value
                ticker_data_list.append(ticker_data)

            # Condicional para evitar problemas con el nombre pirate chain
            if crypto_id == "pirate-chain":
                crypto_id = "pirate_chain"

            # Usando los datos adicionados en ticker_data_list, guardamos el dataframe en el diccionario a tal fin
            dataframes[f"df_{crypto_id}_ticker"] = pd.DataFrame(ticker_data_list)
        else:
            return f"El llamado al endpoint para {crypto_id} falló con código de error {response.status_code}"
        
    # Retornamos el diccionario de dataframes    
    return dataframes


def get_coin_history(crypto_id, date):
    """ Llamado al endpoint de datos históricos. Resultado limitado a prices, market caps y total volumes"""

    # URL de la consulta API, con placeholder para la moneda
    base_url = "https://api.coingecko.com/api/v3/coins/{}/history?date={}&localization=false"

    url = base_url.format(crypto_id, date)
    # Llamamos al endpoint con los parámetros
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()

        # Creamos un diccionario con las columnas: prices, market_caps, total_volumes
        history_dict = {
            'prices': data['market_data']['current_price']['usd'],
            'market_caps':  data['market_data']['market_cap']['usd'],
            'total_volumes': data['market_data']['total_volume']['usd'] 
        }
    else:
        return f"El llamado al endpoint para {crypto_id} falló con código de error {response.status_code}"
    
    return history_dict


def get_market_chart_max(crypto_ids):
    """ Llamado al endpoint de datos de mercado, utilizando el máximo de días para la moneda consultada """

    dataframes = dict()

    # URL de la consulta API, con placeholder para la moneda
    base_url = "https://api.coingecko.com/api/v3/coins/{}/market_chart?vs_currency=USD&days=max"

    for call, crypto_id in enumerate(crypto_ids):
        # Evitmaos error 429
        if call > 9:
            sleep(60)

        # Formamos la URL usando la variable 
        url = base_url.format(crypto_id)
        # Llamamos al endpoint
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            # Creamos un diccionario con las columnas: date, prices, market_caps, total_volumes
            df_dict = {
                'date': [datetime.utcfromtimestamp(entry[0] / 1000) for entry in data['prices']],
                'prices': [entry[1] for entry in data['prices']],
                'market_caps': [entry[1] for entry in data['market_caps']],
                'total_volumes': [entry[1] for entry in data['total_volumes']]
            }

            # Condicional para evitar problemas con el nombre pirate chain
            if crypto_id == "pirate-chain":
                crypto_id = "pirate_chain"

            # Guardamos el dataframe
            dataframes[f"df_{crypto_id}_max"] = pd.DataFrame(df_dict)

        else:
             return f"El llamado al endpoint para {crypto_id} falló con código de error {response.status_code}"

    return dataframes


def get_market_chart_interval(crypto_ids, older_date=None, recent_date=None):
    """ Llamado al endpoint de datos de mercado, utilizando el intervalod dee días indicado para la moneda consultada """
    
    if not recent_date:
        recent_date = datetime.now()
    if not older_date:
        older_date = recent_date - relativedelta(years=1)
    recent_unix = int(recent_date.timestamp())
    older_unix = int(older_date.timestamp())

    dataframes = dict()

    # URL de la consulta API, con los placeholders para las variables
    base_url = "https://api.coingecko.com/api/v3/coins/{}/market_chart/range?vs_currency=USD&from={}&to={}"

    # Loop para recorrer la lista de IDs de monedas crypto
    for call, crypto_id in enumerate(crypto_ids):
        # Evitamos error 429
        if call > 9:
            sleep(60)

        # Formamos la URL usando las variables 
        url = base_url.format(crypto_id, older_unix, recent_unix)
        # Llamamos al endpoint con los parámetros
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            # Creamos un diccionario con las columnas: date, prices, market_caps, total_volumes
            df_dict = {
                'date': [datetime.utcfromtimestamp(entry[0] / 1000) for entry in data['prices']],
                'prices': [entry[1] for entry in data['prices']],
                'market_caps': [entry[1] for entry in data['market_caps']],
                'total_volumes': [entry[1] for entry in data['total_volumes']]
            }



            # Condicional para evitar problemas con el nombre pirate chain
            if crypto_id == "pirate-chain":
                crypto_id = "pirate_chain"
                
            # Creamos un Dataframe con el diccionario
            dataframes[f"df_{crypto_id}_interval"] = pd.DataFrame(df_dict)

        else:
            return f"El llamado al endpoint falló con código de error {response.status_code}"

    return dataframes


def get_OHLC(crypto_ids, days='max'):
    """ Llamado al endpoint de open, high, low, close"""

    dataframes = dict()

    # URL base para OHLC con rango de días (max es el valor por defecto)
    base_url = "https://api.coingecko.com/api/v3/coins/{}/ohlc?vs_currency=USD&days={}"

    # Loop para recorrer la lista de IDs de monedas crypto
    for call, crypto_id in enumerate(crypto_ids):
        # Evitamos error 429
        if call > 9:
            sleep(60)

        url = base_url.format(crypto_id, days)
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            df_dict = {
                'date': [datetime.utcfromtimestamp(entry[0] / 1000) for entry in data],
                'open': [entry[1] for entry in data],
                'high': [entry[2] for entry in data],
                'low': [entry[3] for entry in data],
                'close': [entry[4] for entry in data]
            }

            # Condicional para evitar problemas con el nombre pirate chain
            if crypto_id == "pirate-chain":
                crypto_id = "pirate_chain"

            # Agregamos el dataframe al diccionario
            dataframes[f"df_{crypto_id}_ohlc"] = pd.DataFrame(df_dict)
        else:
             return f"El llamado al endpoint para {crypto_id} falló con código de error {response.status_code}"
    
    return dataframes


# CoinMarketCap

def get_metadata_v2(crypto_ids):

    # Base de la URL
    base_url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/info"
    # Parámetros
    params = {
        "slug": ",".join(crypto_ids),
    }

    response = session.get(base_url, params=params)

    if response.status_code == 200:
        data = response.json()

        df = pd.DataFrame(data['data']).T
        df.reset_index(drop=True, inplace=True)

        return df
    else:
        return f"El llamado al endpoint falló con código de error {response.status_code}"

    
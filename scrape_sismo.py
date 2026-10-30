
import requests
from bs4 import BeautifulSoup
import boto3
import uuid
import json


def lambda_handler(event, context):

    # URL de la página web del IGP
    url = "https://ultimosismo.igp.gob.pe/productos/reportes-sismicos"

    # Realizar la solicitud HTTP a la página web
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=25
    )

    if response.status_code != 200:
        return {
            'statusCode': response.status_code,
            'body': 'Error al acceder a la página web'
        }

    # Parsear el contenido HTML de la página web
    soup = BeautifulSoup(response.content, 'html.parser')

    # Encontrar la tabla que contiene los reportes sísmicos
    table = None

    for current_table in soup.find_all('table'):

        headers = [
            header.get_text(" ", strip=True)
            for header in current_table.find_all('th')
        ]

        if any('Cod reporte' in header for header in headers):
            table = current_table
            break

    if not table:
        return {
            'statusCode': 404,
            'body': 'No se encontró la tabla de reportes sísmicos'
        }

    # Extraer los encabezados de la tabla
    headers = [
        header.get_text(" ", strip=True)
        for header in table.find_all('th')
    ]

    # Extraer las primeras 10 filas
    rows = []

    for row in table.find_all('tr'):

        cells = row.find_all('td')

        if not cells:
            continue

        # Extraer los datos de cada celda
        values = [
            cell.get_text(" ", strip=True)
            for cell in cells
        ]

        if len(values) != len(headers):
            continue

        # Crear un diccionario con encabezados y valores
        data = dict(zip(headers, values))

        # Extraer el enlace del reporte sísmico
        link = row.find('a', href=True)

        if link:
            data['url_reporte'] = link['href']

        rows.append(data)

        # Limitar a los 10 últimos sismos
        if len(rows) == 10:
            break

    if not rows:
        return {
            'statusCode': 404,
            'body': 'No se encontraron registros sísmicos'
        }

    # Guardar los datos en DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('TablaSismosIGP')

    # Eliminar todos los elementos anteriores
    scan = table.scan()

    with table.batch_writer() as batch:

        for each in scan['Items']:
            batch.delete_item(
                Key={
                    'id': each['id']
                }
            )

    # Insertar los nuevos datos
    i = 1

    for row in rows:

        row['#'] = i
        row['id'] = str(uuid.uuid4())

        table.put_item(Item=row)

        i = i + 1

    # Retornar el resultado como JSON
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps(rows, ensure_ascii=False)
    }

import requests
import boto3
import uuid
import json
from datetime import datetime


def lambda_handler(event, context):

    # La página del IGP arma su tabla con JavaScript, pero los datos salen de
    # esta API JSON (un arreglo con todos los reportes del año):
    # https://ultimosismo.igp.gob.pe/api/ultimo-sismo/ajaxb/<año>
    url_base = "https://ultimosismo.igp.gob.pe/api/ultimo-sismo/ajaxb/"

    anio = datetime.now().year
    sismos = []

    # Se consulta el año actual y, si aún no hay 10 reportes
    # (por ejemplo a inicios de enero), también el año anterior
    for anio_consulta in [anio, anio - 1]:

        response = requests.get(
            url_base + str(anio_consulta),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=25
        )

        if response.status_code != 200:
            return {
                'statusCode': response.status_code,
                'body': 'Error al acceder a la API del IGP'
            }

        sismos.extend(response.json())

        if len(sismos) >= 10:
            break

    if not sismos:
        return {
            'statusCode': 404,
            'body': 'No se encontraron registros sísmicos'
        }

    # La API devuelve del más antiguo al más reciente:
    # se ordena de forma descendente y se toman los 10 últimos sismos
    sismos.sort(key=lambda s: s.get('idlistasismos', 0), reverse=True)
    sismos = sismos[:10]

    # Armar las filas que se guardarán (misma idea de la tabla de clase)
    rows = []
    i = 1

    for s in sismos:
        rows.append({
            'id': str(uuid.uuid4()),
            '#': i,
            'Cod reporte': s.get('codigo', ''),
            'Referencia': s.get('referencia', ''),
            'Magnitud': s.get('magnitud', ''),
            'Profundidad': s.get('profundidad', ''),
            'Latitud': s.get('latitud', ''),
            'Longitud': s.get('longitud', ''),
            'Intensidad': s.get('intensidad', ''),
            'Fecha local': s.get('fecha_local', '')[:10],
            'Hora local': s.get('hora_local', '')[11:19],
            'Reporte PDF': s.get('reporte_acelerometrico_pdf', '')
        })
        i = i + 1

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
    for row in rows:
        table.put_item(Item=row)

    # Retornar el resultado como JSON
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps(rows, ensure_ascii=False)
    }


import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://datos.madrid.es/api/3/action/datastore_search"

PARAMETROS = {
    "limit": 5,
    "resource_id": "300076-11-deportes-ocupacion-csv",
}


def probar_api() -> None:
    """Consulta cinco registros de ocupación publicados por Madrid."""
    url = f"{BASE_URL}?{urlencode(PARAMETROS)}"
    peticion = Request(
        url,
        headers={"User-Agent": "PB2-Agente-Deportes/1.0"},
    )

    print("Consultando la API municipal...")
    print(f"Fuente: {PARAMETROS['resource_id']}")

    try:
        with urlopen(peticion, timeout=10) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))

        if not datos.get("success"):
            print("ERROR: el servicio no ha confirmado la consulta.")
            return

        resultado = datos.get("result", {})
        registros = resultado.get("records", [])

        print("\nCONEXIÓN CORRECTA")
        print(f"Registros recibidos: {len(registros)}")
        print(f"Total publicado por el servicio: {resultado.get('total')}")

        if not registros:
            print("La consulta ha funcionado, pero no hay registros.")
            return

        print("\nCampos disponibles:")
        print(", ".join(registros[0].keys()))

        print("\nPrimer registro (resumen):")
        campos = [
            "Ano",
            "Mes",
            "Clase",
            "Actividad",
            "Distrito",
            "Centro deportivo",
            "No Plazas Ofertadas",
            "No Plazas Ocupadas",
            "No Plazas Libres",
        ]

        for campo in campos:
            print(f"- {campo}: {registros[0].get(campo, 'No disponible')}")

    except HTTPError as error:
        print(f"ERROR HTTP: el servicio respondió con código {error.code}.")
    except URLError as error:
        print(f"ERROR DE CONEXIÓN: {error.reason}")
    except TimeoutError:
        print("ERROR: la consulta ha superado los 10 segundos.")
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("ERROR: la respuesta del servicio no contiene JSON válido.")
    except (KeyError, AttributeError, TypeError):
        print("ERROR: la respuesta no tiene la estructura esperada.")


if __name__ == "__main__":
    probar_api()

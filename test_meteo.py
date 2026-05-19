from tools.meteo_tool import get_meteo_domani



if __name__ == "__main__":
    print(get_meteo_domani.invoke({"city": "bareggio"}))
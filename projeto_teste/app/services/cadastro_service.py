
class CadastroService:

    @staticmethod
    def normalizar_dados(form, colunas_map, campos_numericos):

        dados = {}

        for form_name, db_name in colunas_map.items():
            valor = form.get(form_name, '')

            if db_name in campos_numericos:
                dados[db_name] = int(valor) if valor.isdigit() else 0
            else:
                dados[db_name] = valor or '-'

        return dados

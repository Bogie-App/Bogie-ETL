class GTFSStationRepository:
    def __init__(self, df_metro):
        self._df_metro = df_metro

    # return la liste triée des noms de lignes de métro
    def list_line_names(self):
        df_routes_metro = self._df_metro[['route_short_name']].drop_duplicates()
        line_names = sorted(df_routes_metro['route_short_name'].unique())
        return line_names

    # return les rows du dataframe pour une ligne donnée
    def get_line_stop_rows(self, line_name):
        subset = self._df_metro[
            self._df_metro['route_short_name'].astype(str) == line_name
        ].copy()
        return subset

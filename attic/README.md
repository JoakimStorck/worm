# attic -- den gamla Bokeh-appen

Inget här importeras av körningen, analysen eller testerna. Filerna ligger kvar
för att läsas, inte för att köras.

Appen var en Bokeh-serverapp som skulle spela upp en körning i fyra paneler.
Den blev aldrig färdig: `ReplayController.apply_event` är en attrapp
(`# TODO: implementera faktisk logik` följt av `pass`), så tidslinjen visade
samma bild i varje steg. Vägen in var trasig på två sätt till --
`ScenarioResult.from_run` läste `final_state_*` och lämnade det som
starttillstånd, och eventloggen lästes med `pd.read_csv` trots att den är rader
av nyckel-värde-par med varierande antal fält.

Den ersätts av `scripts/export_viz.py` plus en fristående visningsapp. Skälet
till att spara filerna är `visualization/map_panel.py` och
`visualization/occupation_space_panel.py`: de är den enda skrivna
dokumentationen av hur kartan och det polära rummet faktiskt ritats -- urval,
färgsättning, hovertexter, hur kompetenscirkeln kopplas till markeringen. Det
är läsmaterial när panelerna byggs om, inte kod att återuppliva.

`core/visualization/paperstyle.py` ligger kvar i `core/`: den används av
`scripts/figures.py` och har inget med appen att göra.

Kan raderas när visningsappen är klar och inget av innehållet behövs som
referens längre.

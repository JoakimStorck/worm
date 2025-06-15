from bokeh.plotting import figure
from bokeh.io import curdoc

p = figure(title="Standalone Demo", width=400, height=400)
p.circle([1, 2, 3], [4, 5, 6], size=10)  # <--- lägg till size!
curdoc().add_root(p)
curdoc().title = "Test Bokeh"

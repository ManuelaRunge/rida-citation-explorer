"""Chronological Plotly network; unknown years occupy a labelled separate column."""
import html
import plotly.graph_objects as go


def figure(result):
    nodes = sorted(result['nodes'], key=lambda n: (n['year'] is None, n['year'] or 0, n['id']))
    years = [n['year'] for n in nodes if n['year'] is not None]
    unknown = max(years, default=2000) + 2
    positions, slots = {}, {}
    for n in nodes:
        year = n['year'] if n['year'] is not None else unknown
        slot = slots.get(year, 0)
        slots[year] = slot + 1
        positions[n['id']] = (year, slot)
    fig = go.Figure()
    for e in result['edges']:
        x1, y1 = positions[e['citing']]
        x2, y2 = positions[e['cited']]
        fig.add_trace(go.Scatter(x=[x1, x2], y=[y1, y2], mode='lines', line=dict(color='#a9b9bb', width=1),
                                text=f"{e['citing']} → {e['cited']} · OpenAlex", hoverinfo='text', showlegend=False))
        fig.add_annotation(x=x2, y=y2, ax=x1, ay=y1, xref='x', yref='y', axref='x', ayref='y',
                           text='', showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1, arrowcolor='#a9b9bb')
    fig.add_trace(go.Scatter(x=[positions[n['id']][0] for n in nodes], y=[positions[n['id']][1] for n in nodes],
        mode='markers', marker=dict(size=[18 if n['analysis']['role'] == 'seed' else 11 for n in nodes],
        color=['#D89A2B' if n['analysis']['role'] == 'seed' else '#002531' for n in nodes]),
        text=[html.escape(f"{n['id']} · {n['year'] or 'Unknown year'} · {n['title']}") for n in nodes], hoverinfo='text', showlegend=False))
    ticks = sorted(set(years)) + ([unknown] if any(n['year'] is None for n in nodes) else [])
    fig.update_layout(height=520, paper_bgcolor='#F6F1E8', plot_bgcolor='#F6F1E8',
                      xaxis=dict(title='Publication year (not development of ideas)', tickvals=ticks,
                                 ticktext=['Unknown' if t == unknown else str(t) for t in ticks]),
                      yaxis=dict(visible=False), margin=dict(l=20, r=20, t=20, b=50))
    return fig

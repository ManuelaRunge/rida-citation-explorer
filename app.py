import streamlit as st
from research_roots.api import Sources, Client, APIError
from research_roots.pipeline import Settings, build
from research_roots.analysis import filter_graph, citation_path
from research_roots.exports import bundle
from research_roots.visualization import figure

st.set_page_config(page_title='RIDA Research Roots', page_icon='🌱', layout='wide')
st.title('RIDA Research Roots')
st.caption('Explore publication chronology and traceable citation relationships.')
if 'sources' not in st.session_state:
    st.session_state.sources = Sources(Client())
with st.sidebar:
    st.header('Explore a publication')
    with st.form('lookup'):
        identifier = st.text_input('DOI, PMID, or OpenAlex ID', '35300707')
        depth = st.slider('Reference depth', 0, 2, 2)
        nodes = st.slider('Maximum publications', 10, 200, 80)
        refs = st.slider('References per publication', 1, 50, 20)
        citing = st.slider('Subsequent citing publications', 0, 100, 20)
        refresh = st.checkbox('Refresh source data (ignore one-hour session cache)')
        submitted = st.form_submit_button('Build lineage', type='primary')
    st.caption('OpenAlex citation graph; Europe PMC seed metadata cross-check. Limits can omit relevant publications.')
if submitted:
    if refresh:
        st.session_state.sources.client.cache.clear()
    try:
        with st.spinner('Resolving publication and retrieving citation evidence…'):
            st.session_state.result = build(identifier, Settings(depth, nodes, 400, refs, citing), st.session_state.sources)
    except (APIError, ValueError) as exc:
        st.error(str(exc))
        st.session_state.pop('result', None)
st.info('A citation is a bibliographic relationship. Paths and shared ancestors do not establish intellectual influence. Missing edges do not establish absence of a citation; completeness is unknown.')
if 'result' not in st.session_state:
    st.stop()
result = st.session_state.result
seed = next(n for n in result['nodes'] if n['id'] == result['manifest']['seed'])
st.subheader(seed['title'])
st.write(', '.join(seed['authors']))
st.caption(f"{seed['year'] or 'Unknown year'} · {seed['journal'] or 'Unknown source'} · {seed['id']}")
with st.expander('Seed metadata and source counts'):
    st.json({k: v for k, v in seed.items() if k != 'source_records'})
years = [n['year'] for n in result['nodes'] if n['year'] is not None]
c1, c2, c3 = st.columns(3)
direction = c1.selectbox('Citation direction', ['all', 'references', 'citing'])
view_depth = c2.selectbox('Display depth', [2, 1, 0])
pub_type = c3.selectbox('Publication type', ['all'] + sorted({n['type'] for n in result['nodes'] if n.get('type')}))
period = st.slider('Publication years', min(years), max(years), (min(years), max(years))) if years and min(years) < max(years) else (None, None)
unknown = st.checkbox('Include publications with unknown year', True)
view = filter_graph(result, *period, direction, view_depth, pub_type, unknown)
network, timeline, details, evidence, exports = st.tabs(['Citation network', 'Chronology & indicators', 'Inspect & trace', 'Evidence', 'Export'])
fig = figure(view)
with network:
    st.plotly_chart(fig, width='stretch')
    st.caption('Gold marks the seed. Arrows run from citing to cited works. Hover for details; use Inspect & trace for full records.')
with timeline:
    rows = [{'id': n['id'], 'year': n['year'], 'title': n['title'], **n['analysis']} for n in sorted(view['nodes'], key=lambda n: (n['year'] is None, n['year'] or 0, n['id']))]
    st.dataframe(rows, hide_index=True)
    st.caption('Indicators are computed on the full retrieved network before display filters. Shared ancestors occur in at least two seed-reference branches. Reachable citing works counts unique works with a citation path to the publication. These are subset-dependent heuristics, not scientific importance scores.')
with details:
    labels = {n['id']: n for n in view['nodes']}
    if labels:
        selected = st.selectbox('Publication', list(labels), format_func=lambda k: f"{k} — {labels[k]['title']}")
        st.json(labels[selected])
        target = st.selectbox('Find a directed citation path to', list(labels))
        path = citation_path(view, selected, target)
        st.write(' → '.join(path) if path else 'No directed path in this filtered subset.')
with evidence:
    st.json(view['manifest'])
    st.write('Retrieval issues and limits')
    st.json(result['issues'])
    st.write('Direct citation evidence')
    st.json(view['edges'])
with exports:
    st.download_button('Download filtered exploration (ZIP)', bundle(view, fig.to_html(include_plotlyjs=True)), 'research-roots.zip', 'application/zip')
    st.caption('Includes nodes, edges and publication CSVs, lineage JSON, manifest, Markdown summary and standalone interactive HTML. Source metadata and retrieval timestamps are preserved in JSON.')

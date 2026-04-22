import os
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flasgger import Swagger
from graph_db import Neo4jManager
from normalizer import normalize_entity

from ocr import perform_ocr
from htr import perform_htr
from ner import perform_ner, translate_text, extract_entities_structured
from relations import extract_relations

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

swagger_template = {
    "swagger": "2.0",
    "info": {"title": "AI Archive API", "version": "1.0.0"},
    "consumes": ["multipart/form-data"],
    "produces": ["application/json"]
}
swagger = Swagger(app, template=swagger_template)

db = Neo4jManager()


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'image' not in request.files or 'text_type' not in request.form:
            return redirect(request.url)

        file = request.files['image']
        text_type = request.form['text_type']
        translate = 'translate' in request.form

        if file and file.filename and text_type in ['ocr', 'htr']:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)

            try:
                text = perform_ocr(filepath) if text_type == 'ocr' else perform_htr(filepath)[1]
                if translate:
                    text = translate_text(text)

                annotated_html = perform_ner(text)
                entities = extract_entities_structured(text)
                relations = extract_relations(text, entities)

                norm_entities = [normalize_entity(e) for e in entities]
                try:
                    db.upsert_entities(norm_entities)
                    db.upsert_relations(relations)
                except Exception:
                    pass

                session['last_result'] = {
                    'image_path': url_for('static', filename=f'uploads/{file.filename}'),
                    'extracted_text': annotated_html,
                    'text_type': text_type,
                    'translate': translate,
                    'relations': relations,
                    'raw_text': text
                }
                return redirect(url_for('results'))
            except Exception:
                return redirect(url_for('index'))

    return render_template('index.html')


@app.route('/results')
def results():
    result = session.get('last_result')
    if not result or not result.get('image_path'):
        return redirect(url_for('index'))
    return render_template('results.html', **result)


@app.route('/ner_check', methods=['GET', 'POST'])
def ner_check():
    extracted_text = None
    relations = []
    translate = False
    if request.method == 'POST':
        text = request.form.get('text', '')
        translate = 'translate' in request.form
        if text:
            if translate:
                text = translate_text(text)
            entities = extract_entities_structured(text)
            extracted_text = perform_ner(text)
            relations = extract_relations(text, entities)
    return render_template('ner_check.html',
                           extracted_text=extracted_text,
                           relations=relations,
                           translate=translate)


@app.route('/api/process', methods=['POST'])
def api_process():
    if 'image' not in request.files or 'text_type' not in request.form:
        return jsonify({'error': 'Missing required fields'}), 400

    file = request.files['image']
    text_type = request.form['text_type']
    translate = 'translate' in request.form

    if not file.filename or text_type not in ['ocr', 'htr']:
        return jsonify({'error': 'Invalid input'}), 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    text = perform_ocr(filepath) if text_type == 'ocr' else perform_htr(filepath)[1]
    if translate:
        text = translate_text(text)

    annotated_text = perform_ner(text)
    entities = extract_entities_structured(text)
    relations = extract_relations(text, entities)

    return jsonify({
        'text': text,
        'annotated_text': annotated_text,
        'relations': relations
    })


@app.route('/api/query', methods=['POST'])
def api_query():
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Query is required'}), 400

    try:
        with db.driver.session() as sess:
            records = list(sess.run(query))
        
        nodes, edges, table_rows = [], [], []
        node_ids = set()

        for record in records:
            row = {}
            for key in record.keys():
                val = record[key]
                
                # 1. Это Узел (Node)
                if hasattr(val, 'labels'):
                    nid = val.element_id
                    if nid not in node_ids:
                        node_ids.add(nid)
                        lbls = list(val.labels)
                        label = lbls[0] if lbls else 'Node'
                        nodes.append({'id': nid, 'label': val.get('name') or val.get('value') or label, 'type': label})
                    row[key] = f"({label}) {val.get('name') or val.get('value')}"
                
                # 2. Это Связь (Relationship)
                elif hasattr(val, 'type') and hasattr(val, 'start_node'):
                    start_nid = val.start_node.element_id
                    end_nid = val.end_node.element_id
                    
                    if start_nid not in node_ids:
                        node_ids.add(start_nid)
                        start_label = list(val.start_node.labels)[0] if val.start_node.labels else 'Node'
                        nodes.append({'id': start_nid, 'label': val.start_node.get('name') or start_label, 'type': start_label})
                    
                    if end_nid not in node_ids:
                        node_ids.add(end_nid)
                        end_label = list(val.end_node.labels)[0] if val.end_node.labels else 'Node'
                        nodes.append({'id': end_nid, 'label': val.end_node.get('name') or end_label, 'type': end_label})

                    edges.append({'from': start_nid, 'to': end_nid, 'type': val.type})
                    row[key] = f"-[:{val.type}]->"
                
                # 3. Это Путь (Path) - ИСПРАВЛЕНИЕ ОШИБКИ JSON
                elif hasattr(val, 'nodes'):
                    for node in val.nodes:
                        nid = node.element_id
                        if nid not in node_ids:
                            node_ids.add(nid)
                            lbls = list(node.labels)
                            label = lbls[0] if lbls else 'Node'
                            nodes.append({'id': nid, 'label': node.get('name') or node.get('value') or label, 'type': label})
                    
                    for rel in val.relationships:
                        edges.append({
                            'from': rel.start_node.element_id,
                            'to': rel.end_node.element_id,
                            'type': rel.type
                        })
                    row[key] = "Path"
                
                # 4. Всё остальное (текст, числа)
                else:
                    row[key] = str(val)
            
            table_rows.append(row)

        return jsonify({'results': table_rows, 'graph_nodes': nodes, 'graph_edges': edges})
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/graph', methods=['GET'])
def api_get_graph():
    try:
        cypher = """
            MATCH (n)
            OPTIONAL MATCH (n)-[r]->(m)
            RETURN 
                elementId(n) AS n_id, labels(n) AS n_labels, n.name AS n_name, n.value AS n_value,
                elementId(r) AS r_id, type(r) AS r_type,
                elementId(m) AS m_id, labels(m) AS m_labels, m.name AS m_name, m.value AS m_value
        """
        with db.driver.session() as sess:
            records = list(sess.run(cypher))

        nodes_map, nodes, edges = {}, [], []
        for rec in records:
            n_id, m_id = rec.get('n_id'), rec.get('m_id')
            r_id = rec.get('r_id')
            
            if n_id:
                key = f"{rec['n_labels'][0]}_{n_id}"
                if key not in nodes_map:
                    nodes_map[key] = True
                    nodes.append({'id': key, 'label': rec.get('n_name') or rec.get('n_value'), 'type': rec['n_labels'][0]})
            if m_id:
                key = f"{rec['m_labels'][0]}_{m_id}"
                if key not in nodes_map:
                    nodes_map[key] = True
                    nodes.append({'id': key, 'label': rec.get('m_name') or rec.get('m_value'), 'type': rec['m_labels'][0]})
            if r_id:
                edges.append({'from': f"{rec['n_labels'][0]}_{n_id}", 'to': f"{rec['m_labels'][0]}_{m_id}", 'type': rec.get('r_type')})
        
        return jsonify({'nodes': nodes, 'edges': edges})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
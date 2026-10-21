"""Read-only graph projection of explicit catalog relations.

The page size applies to the selected collection, not to the relationships of
an item.  A source or pathway therefore retains every matching linked record.
Directory entries with no recorded relations remain visible as isolated nodes.
"""
import hashlib
import json

from catalog_queries import Catalog, rows


NUMERIC = ('toxicity', 'properties', 'environment', 'bioactivity')
OBSERVATION_COLUMNS = (
    'record_id,provider,source_key,domain,property_name,value,value_text,unit,'
    'qualifier,value_min,value_max,temperature_c,ph,medium,species,taxon_id,'
    'exposure_conditions,target_id,support_type,assertion_kind,source_support_code,'
    'review_status,method,derivation,reference,source_url,asset_path,source_row'
)
NETWORK_OBSERVATION_COLUMNS = (
    'record_id,provider,source_key,domain,property_name,species,taxon_id,'
    'target_id,support_type,assertion_kind,reference,source_url'
)
MEMBER_SUPPORT = "CASE WHEN a.provider='KEGG' OR ma.annotation_code='IEA' THEN 'inferred_annotation' ELSE 'pending_verification' END"


def digest(value):
    return hashlib.sha256(str(value).encode('utf-8')).hexdigest()[:24]


def marks(values):
    return ','.join('?' for _ in values)


def pages(function):
    """Drain a read-only cursor. 500 is only a transport/read batch size."""
    offset = 0
    while True:
        part = function(500, offset)
        yield from part.get('matches', [])
        count = part.get('returned', 0)
        if not part.get('has_more') or not count:
            break
        offset += count


class Graph:
    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.related_records = set()

    def node(self, key, kind, label, record=None, detail_kind=None):
        if not key:
            return None
        key = str(key)
        new = {'id': key, 'kind': kind, 'label': str(label or key),
               'display_name': str(label or key), 'record': record,
               'detail_kind': detail_kind}
        old = self.nodes.get(key)
        if old:
            if old.get('record') and not record:
                new['record'] = old['record']
            if old.get('detail_kind') and not detail_kind:
                new['detail_kind'] = old['detail_kind']
            if new['label'] == key and old.get('label'):
                new['label'] = new['display_name'] = old['label']
        self.nodes[key] = new
        return key

    def edge(self, source, target, relation, record, basis):
        if not source or not target or source == target:
            return
        key = 'relation:' + hashlib.sha256(json.dumps(
            [source, target, relation, record.get('record_id')], ensure_ascii=False).encode()).hexdigest()
        self.edges[key] = {
            'id': key, 'source': source, 'target': target, 'relation': relation,
            'basis': basis, 'support_type': record.get('support_type', 'pending_verification'),
            'record_id': record.get('record_id'), 'source_url': record.get('source_url'),
            'record': record,
            'measurement_ids': [record['record_id']] if record.get('domain') in NUMERIC else [],
        }
        if record.get('record_id'):
            self.related_records.add(record['record_id'])

    def observation(self, record, chemical_ids=None):
        rid = record['record_id']
        domain = record.get('domain', 'toxicity')
        observation = self.node(rid, 'study', record.get('reference') or rid, record, domain)
        if chemical_ids is None:
            identities = record.get('identifiers') or []
            identity = next((i for i in identities if i['namespace'] == 'PubChemCID'),
                            next((i for i in identities if i['namespace'] == 'CAS'),
                                 next(iter(identities), None)))
            if identity:
                identifier = str(identity['identifier'])
                key = 'PubChemCID:' + identifier if identity['namespace'] == 'PubChemCID' else identifier
                self.node(key, 'chemical', record.get('chemical_name') or key,
                          {'source_id': key}, 'chemicals')
                chemical_ids = [key]
        for chemical in chemical_ids or []:
            self.edge(chemical, observation, '资料记录', record, 'source_identifier')
        if record.get('species') or record.get('taxon_id'):
            key = 'taxon:' + str(record['taxon_id']) if record.get('taxon_id') else 'species:' + str(record['species'])
            taxon = self.node(key, 'organism', record.get('species') or 'TaxID ' + str(record['taxon_id']))
            self.edge(observation, taxon, '实验物种', record, 'measurement')
        if record.get('property_name'):
            endpoint = self.node('endpoint:' + digest([domain, record['property_name']]),
                                 'endpoint', record['property_name'])
            self.edge(observation, endpoint, '测量指标', record, 'measurement')
        if record.get('target_id'):
            target = self.node('target:' + str(record['target_id']), 'protein', record['target_id'])
            self.edge(observation, target, '原记录靶点', record, 'source_target_annotation')
        return observation

    def member(self, record, focus=None, focus_kind=None):
        r = dict(record)
        r['record_id'] = 'pathway-membership:' + digest([r['pathway_id'], r['external_member_id']])
        r['assertion_kind'] = 'pathway_membership'
        pathway = self.node(r['pathway_id'], 'role', r.get('pathway_name') or r['pathway_id'],
                            {'pathway_id': r['pathway_id']}, 'pathways')
        links = json.loads(r.pop('member_links_json', '[]') or '[]')
        genes = {x['entity_id'] for x in links if x['entity_type'] == 'gene'}
        proteins = {x['entity_id'] for x in links if x['entity_type'] == 'protein'}
        if r.get('gene_id'):
            genes.add(r['gene_id'])
        if r.get('protein_id'):
            proteins.add(r['protein_id'])
        r['source_member_links'] = links
        if focus:
            if focus_kind == 'genes':
                genes.add(focus)
            elif focus_kind == 'proteins':
                proteins.add(focus)
        for gene in sorted(genes):
            gene_node = self.node(gene, 'gene', r.get('gene_symbol') if gene == r.get('gene_id') else gene,
                                  {'gene_id': gene}, 'genes')
            self.edge(pathway, gene_node, '通路成员注释', r, 'pathway_membership')
        for protein in sorted(proteins):
            protein_node = self.node(protein, 'protein', protein, {'protein_id': protein}, 'proteins')
            self.edge(pathway, protein_node, '通路成员注释', r, 'pathway_membership')
        if not genes and not proteins:
            # Unresolved provider identifiers remain members; they are not
            # silently removed or made into a fabricated local gene/protein.
            external = str(r['external_member_id'])
            is_protein = external.startswith(('UniProt:', 'UniProtKB:'))
            member = self.node('pathway-member:' + external,
                               'protein' if is_protein else 'gene', external,
                               {'external_member_id': external, 'provider': r.get('provider')})
            self.edge(pathway, member, '来源通路成员', r, 'pathway_membership')


def member_records(catalog, pathway_ids=None, entity_id=None, support='default', entity_ids=None, external_member_id=None):
    types = catalog.types('pathways', support)
    sql = '''SELECT m.*,g.name AS gene_symbol,t.scientific_name,t.ncbi_taxid,
        p.name AS pathway_name,a.provider,a.source_url,ma.annotation_code,
        (SELECT json_group_array(json_object('entity_type',l.entity_type,
             'entity_id',l.entity_id,'relation',l.relation))
         FROM pathway_member_links l WHERE l.pathway_id=m.pathway_id
           AND l.external_member_id=m.external_member_id) AS member_links_json,'''
    sql += MEMBER_SUPPORT + ''' AS support_type
        FROM pathway_source_members m JOIN pathways p USING(pathway_id)
        JOIN pathway_annotations a USING(pathway_id)
        JOIN taxa t ON t.taxon_id=m.taxon_id
        LEFT JOIN genes g ON g.gene_id=m.gene_id
        LEFT JOIN pathway_member_annotations ma
          ON ma.pathway_id=m.pathway_id AND ma.external_member_id=m.external_member_id
        WHERE ''' + MEMBER_SUPPORT + ' IN (' + marks(types) + ')'
    args = list(types)
    if pathway_ids is not None:
        if not pathway_ids:
            return
        sql += ' AND m.pathway_id IN (SELECT value FROM json_each(?))'
        args.append(json.dumps(pathway_ids))
    if entity_id:
        table = 'lookup.entity_pathways' if catalog.has_lookup else 'pathway_member_links'
        sql += ' AND (m.pathway_id,m.external_member_id) IN (SELECT pathway_id,external_member_id FROM ' + table + ' WHERE entity_id=?)'
        args.append(entity_id)
    if entity_ids is not None:
        if not entity_ids:return
        table = 'lookup.entity_pathways' if catalog.has_lookup else 'pathway_member_links'
        sql += ' AND (m.pathway_id,m.external_member_id) IN (SELECT pathway_id,external_member_id FROM ' + table + ' WHERE entity_id IN (SELECT value FROM json_each(?)))'
        args.append(json.dumps(entity_ids))
    if external_member_id is not None:
        sql+=' AND m.external_member_id=?';args.append(external_member_id)
    sql += ' ORDER BY m.pathway_id,m.external_member_id'
    for row in catalog.fish.execute(sql, args):
        yield dict(row)


def attach_identifiers(catalog, records):
    for record in records:
        record['identifiers'] = rows(catalog.observations,
            'SELECT namespace,identifier FROM identifiers WHERE record_id=? ORDER BY namespace,identifier',
            [record['record_id']])
        yield catalog.resolve_paths(record)


def source_observations(catalog, sources, support, api=None, filters=None, light=False):
    """Use preserved foreign keys, never fuzzy matching of publication titles."""
    if not sources:
        return
    if not any(row[1]=='network_observations' for row in catalog.fish.execute('PRAGMA database_list')):
        catalog.fish.execute('ATTACH DATABASE ? AS network_observations',
                             [catalog.paths['observations'].as_uri() + '?mode=ro'])
    allowed = []
    args = []
    for domain in NUMERIC:
        if api is not None and filters:
            where,params=api.observation_where(catalog,{**filters,'kind':domain,'term':'','support':support})
            allowed.append('('+where.replace('FROM identifiers','FROM network_observations.identifiers')+')')
            args.extend(params)
        else:
            types = catalog.types(domain, support)
            allowed.append('(o.domain=? AND o.support_type IN (' + marks(types) + '))')
            args.extend([domain, *types])
    columns = ','.join('o.' + field for field in (NETWORK_OBSERVATION_COLUMNS if light else OBSERVATION_COLUMNS).split(','))
    sql = 'SELECT ' + columns + ''',m.source_id AS linked_source_id,m.measurement_id AS source_measurement_id
        FROM measurements m JOIN network_observations.observations o
          ON o.record_id='FishSnapshot0.3:'||m.measurement_id
        WHERE (''' + ' OR '.join(allowed) + ') AND m.source_id IN (SELECT value FROM json_each(?))'
    args.append(json.dumps(sources))
    yield from attach_identifiers(catalog, (dict(row) for row in catalog.fish.execute(sql, args)))


def scope_observations(catalog, api, args, *, taxa=None, endpoints=None, light=False):
    """Return every observation explicitly linked to a selected taxon/endpoint."""
    allowed = []
    parameters = []
    named_queries = []
    taxon_names = sorted({r['scientific_name'] for r in (taxa or []) if r.get('scientific_name')})
    taxon_ids = sorted({r['ncbi_taxid'] for r in (taxa or []) if r.get('ncbi_taxid')})
    columns = ','.join('o.' + field for field in (NETWORK_OBSERVATION_COLUMNS if light else OBSERVATION_COLUMNS).split(','))
    for domain in NUMERIC:
        types = catalog.types(domain, args.get('support', 'default'))
        clause = 'o.domain=? AND o.support_type IN (' + marks(types) + ')'
        params = [domain, *types]
        if endpoints is not None:
            names = sorted({r['property_name'] for r in endpoints if r.get('domain') == domain})
            if not names:
                continue
            clause += ' AND o.property_name IN (SELECT value FROM json_each(?))'
            params.append(json.dumps(names))
        if args.get('endpoint'):
            requested=str(args['endpoint']).split('||')
            clause+=' AND o.property_name IN (SELECT value FROM json_each(?))';params.append(json.dumps(requested))
        if args.get('stage'):
            clause+=" AND json_valid(o.exposure_conditions) AND json_extract(o.exposure_conditions,'$.life_stage')=?";params.append(args['stage'])
        if taxa is None and args.get('species'):
            from catalog_queries import filter_values
            selected_species=filter_values(args['species'])
            names=sorted(set(selected_species+[r['scientific_name'] for r in catalog.species_records(selected_species)]))
            clause+=' AND (o.species IN (SELECT value FROM json_each(?)) OR CAST(o.taxon_id AS TEXT) IN (SELECT value FROM json_each(?)))'
            params.extend([json.dumps(names),json.dumps(selected_species)])
        # The collection's search term names a taxon/endpoint, not a chemical.
        if args.get('family'):
            cas = api.family_identifiers(catalog, args['family'])
            if not cas:
                continue
            clause += " AND o.record_id IN (SELECT record_id FROM identifiers WHERE namespace='CAS' AND identifier IN (SELECT value FROM json_each(?)))"
            params.append(json.dumps(cas))
        if taxa is not None:
            # Emit name-index matches immediately. A single final scan retains
            # ID-only/mismatched-name records without duplicates or exclusions.
            named_queries.append((clause+' AND o.species IN (SELECT value FROM json_each(?))',
                                  [*params,json.dumps(taxon_names)]))
            clause+=' AND o.taxon_id IN (SELECT value FROM json_each(?)) AND (o.species IS NULL OR o.species NOT IN (SELECT value FROM json_each(?)))'
            params.extend([json.dumps(taxon_ids),json.dumps(taxon_names)])
        allowed.append('(' + clause + ')')
        parameters.extend(params)
    if not allowed:
        return
    if named_queries:
        available=bool(catalog.observations.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='observation_species'").fetchone())
        hint=' INDEXED BY observation_species' if available else ''
        for where,params in named_queries:
            sql='SELECT '+columns+' FROM observations o'+hint+' WHERE '+where
            yield from attach_identifiers(catalog,(dict(row) for row in catalog.observations.execute(sql,params)))
    # ORDER BY the record primary key made SQLite prefer a broad row lookup
    # over the selective endpoint index (millions of reads for three records).
    # Stable graph identities do not depend on cursor order.
    hint = ' INDEXED BY observation_filter' if endpoints is not None else ' NOT INDEXED'
    sql = 'SELECT ' + columns + ' FROM observations o' + hint + ' WHERE ' + ' OR '.join(allowed)
    yield from attach_identifiers(catalog, (dict(row) for row in catalog.observations.execute(sql, parameters)))


def build_network(api, arguments):
    args = dict(arguments)
    kind = args.get('kind', 'toxicity')
    selected_collection = kind
    # Collection pages are sent by the stream controller until has_more=false.
    # This number never limits relations within a source/pathway.
    args['limit'] = min(500, int(args.get('limit', 100)))
    entity = args.get('entity_id')
    if kind == 'chemicals':
        kind = 'toxicity'
        args['kind'] = kind
        if entity:
            args['term'] = entity
        entity = None
    if kind in NUMERIC and entity:
        with Catalog(api.path) as catalog:
            record = catalog.query('observation', entity)
            selected = [record] if record.get('support_type') in catalog.types(kind, args.get('support', 'default')) else []
            if selected and kind != 'bioactivity':
                record['identifiers'] = rows(catalog.observations,
                    'SELECT namespace,identifier FROM identifiers WHERE record_id=?', [entity])
        result = {'matches': selected, 'returned': len(selected), 'has_more': False, 'offset': 0}
    elif entity and kind in ('sources', 'species', 'pathways', 'genes', 'proteins'):
        with Catalog(api.path) as catalog:
            table, key = {'sources': ('sources', 'source_id'), 'species': ('taxa', 'taxon_id'),
                          'pathways': ('pathways', 'pathway_id'), 'genes': ('genes', 'gene_id'),
                          'proteins': ('proteins', 'protein_id')}[kind]
            selected = rows(catalog.fish, 'SELECT * FROM ' + table + ' WHERE ' + key + '=?', [entity])
        result = {'matches': selected, 'returned': len(selected), 'has_more': False, 'offset': 0}
    else:
        result = api.search(args)
    graph = Graph()
    selected = result.get('matches', [])
    with Catalog(api.path) as catalog:
        if kind in NUMERIC:
            for record in selected:
                graph.observation(record)
        elif kind in ('pathways', 'members'):
            pathway_ids = list(dict.fromkeys(r['pathway_id'] for r in selected))
            for record in selected:
                graph.node(record['pathway_id'], 'role', record.get('name') or record['pathway_id'],
                           record, 'pathways')
            if kind == 'members':
                selected_keys = {(r['pathway_id'], r['external_member_id']) for r in selected}
                members = (r for r in member_records(catalog, pathway_ids, support=args.get('support', 'default'))
                           if (r['pathway_id'], r['external_member_id']) in selected_keys)
            else:
                members = member_records(catalog, pathway_ids, support=args.get('support', 'default'))
            for record in members:
                graph.member(record)
        elif kind in ('genes', 'proteins'):
            field = 'gene_id' if kind == 'genes' else 'protein_id'
            for record in selected:
                key = record[field]
                graph.node(key, 'gene' if kind == 'genes' else 'protein', record.get('name') or key,
                           record, kind)
                for member in member_records(catalog, entity_id=key, support=args.get('support', 'default')):
                    graph.member(member, key, kind)
        elif kind == 'sources':
            for record in selected:
                graph.node(record['source_id'], 'study', record.get('title') or record['source_id'], record, 'sources')
            for record in source_observations(catalog, [r['source_id'] for r in selected], args.get('support', 'default'),api,args):
                observation = graph.observation(record)
                graph.edge(record['linked_source_id'], observation, '来源中的实验记录', record, 'source_measurement_foreign_key')
        elif kind == 'species':
            for record in selected:
                key = 'taxon:' + str(record['ncbi_taxid']) if record.get('ncbi_taxid') else 'species:' + str(record['scientific_name'])
                graph.node(key, 'organism', record['scientific_name'], record, 'species')
            for record in scope_observations(catalog, api, args, taxa=selected):
                graph.observation(record)
        elif kind == 'endpoints':
            for record in selected:
                graph.node('endpoint:' + digest([record['domain'], record['property_name']]),
                           'endpoint', record['property_name'], record)
            for record in scope_observations(catalog, api, args, endpoints=selected):
                graph.observation(record)
        elif kind == 'mechanisms':
            for record in selected:
                record = {**record, 'record_id': record.get('record_id') or record.get('mechanism_id')}
                source = graph.node(record.get('subject'), 'mechanism', record.get('subject'))
                target = graph.node(record.get('object'), 'mechanism', record.get('object'))
                graph.edge(source, target, record.get('predicate'), record,
                           'mechanism_observation' if record.get('support_type') == 'experimental' else 'source_interpretation')
    scope_notes = {
        'chemicals': '毒性实验记录中的关系',
        'sources': '通过来源编号关联的实验记录；保留没有关联测量的来源条目。',
        'species': '观察资料库中按原记录物种关联的实验资料。',
        'endpoints': '观察资料库中按原记录指标关联的资料。',
        'pathways': '所选通路的全部已收录成员注释。',
        'genes': '所选基因的已收录通路成员注释。',
        'proteins': '所选蛋白的已收录通路成员注释。',
    }
    return {'nodes': list(graph.nodes.values()), 'edges': list(graph.edges.values()),
            'records': selected, 'has_more': result.get('has_more', False),
            'offset': result.get('offset', 0), 'returned': result.get('returned', 0),
            'related_record_count': len(graph.related_records), 'query': args,
            'selected_collection': selected_collection, 'relationship_kind': kind,
            'scope_note': scope_notes.get(selected_collection, '当前资料记录中的关系。'),
            'relation_sources': ['observations.sqlite3', 'pathway_source_members', 'pathway_member_links', 'measurements.source_id']}

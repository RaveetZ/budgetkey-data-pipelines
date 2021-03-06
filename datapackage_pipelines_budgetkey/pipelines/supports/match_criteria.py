import logging

from fuzzywuzzy import process,fuzz

from datapackage_pipelines.wrapper import ingest, spew

params, datapackage, resource_iterator = ingest()

criteria = []
cache = {}


def criteria_scorer(supp, crit):
    scores = [
        fuzz.UWRatio(supp[k], crit[k])
        for k in ('purpose', 'office')
        if None not in (supp[k], crit[k])
    ]
    if len(scores) > 0:
        return sum(scores) / len(scores)
    else:
        return 0


def id(x):
    return x

def enrich_supports(rows):
    relevant_rows = 0
    matched_rows = 0
    for row in rows:
        bests = []
        if row['request_type'] == 'א3':
            relevant_rows += 1
            payments = row['payments']
            if payments and len(payments) > 0:
                payment = payments[0]
                key = (payment['support_title'], payment['supporting_ministry'])
                if key in cache:
                    bests = cache[key]
                else:
                    bests = process.extractBests(
                        {
                            'purpose': key[0],
                            'office': key[1]
                        },
                        criteria,
                        processor=id,
                        scorer=criteria_scorer
                    )
                    cache[key] = bests
        if len(bests)>0:
            matched_rows += 1
        row['criteria_docs'] = [x[0] for x in bests]
        yield row
    
    logging.info('MATCH STATS: rel: %d, matched: %d', relevant_rows, matched_rows)


def process_resources(res_iter):
    for res in res_iter:
        if res.spec['name'] == 'criteria':
            criteria.extend(list(res))
            for c in criteria:
                if c['date']:
                    c['date'] = c['date'].isoformat()
        elif res.spec['name'] == 'supports':
            yield enrich_supports(res)
        else:
            yield res


def process_datapackage(dp):
    criteria_res = next(iter(filter(
        lambda r: r['name'] == 'criteria',
        dp['resources']
    )))
    dp['resources'] = list(filter(
        lambda r: r['name'] != 'criteria',
        dp['resources']
    ))
    dp['resources'][-1]['schema']['fields'].append({
        'name': 'criteria_docs',
        'type': 'array',
        'es:itemType': 'object',
        'es:index': False,
        'es:schema': criteria_res['schema']
    })
    return dp


spew(process_datapackage(datapackage),
     process_resources(resource_iterator))
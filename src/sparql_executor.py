from typing import List, Tuple
from SPARQLWrapper import SPARQLWrapper, JSON
import json
import urllib
from pathlib import Path
from tqdm import tqdm

# sparql = SPARQLWrapper("http://10.237.23.185:3001/sparql")
sparql = SPARQLWrapper("http://ekhas037.hpc.iitd.ac.in:3001/sparql")
sparql.setReturnFormat(JSON)
# sparql.setMethod('GET')
# sparql.setTimeout(30000)
# sparql.addParameter("timeout","100000")
# sparql.addParameter("should-sponge", "soft")
# sparql.customHttpHeaders={"timeout":"100000"}
# sparql.parameters = {'timeout':['10000'], 'should-sponge': ['soft']}

path = str(Path(__file__).parent.absolute())

# with open('../ontology/fb_roles', 'r') as f:
#     contents = f.readlines()

# roles = set()
# for line in contents:
#     fields = line.split()
#     roles.add(fields[1])


def execute_query(query: str) -> List[str]:
    sparql.setQuery(query)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query)
        exit(0)
    rtn = []
    for result in results['results']['bindings']:
        assert len(result) == 1  # only select one variable
        for var in result:
            rtn.append(result[var]['value'].replace('http://rdf.freebase.com/ns/', '').replace("-08:00", ''))

    return rtn
    
def execute_query_updated(query: str) -> List[str]:
    sparql.setQuery(query)
    try:
        results = sparql.query().convert()
        # results = sparql.query()
        # print(results)
    except urllib.error.URLError as e:
        print(e)
        print(query)
        exit(0)
    # results = results.convert()
    rtn = []
    for result in results['results']['bindings']:
        # assert len(result) == 1  # only select one variable
        for var in result:
            rtn.append(result[var]['value'].replace('http://rdf.freebase.com/ns/', '').replace("-08:00", ''))

    return results['results']['bindings']


def execute_unary(type: str) -> List[str]:
    query = ("""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX : <http://rdf.freebase.com/ns/> 
    SELECT (?x0 AS ?value) WHERE {
    SELECT DISTINCT ?x0  WHERE {
    """
             '?x0 :type.object.type :' + type + '. '
                                                """
    }
    }
    """)
    # # print(query)
    sparql.setQuery(query)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query)
        exit(0)
    rtn = []
    for result in results['results']['bindings']:
        rtn.append(result['value']['value'].replace('http://rdf.freebase.com/ns/', ''))

    return rtn


def execute_binary(relation: str) -> List[Tuple[str, str]]:
    query = ("""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX : <http://rdf.freebase.com/ns/> 
    SELECT DISTINCT ?x0 ?x1 WHERE {
    """
             '?x0 :' + relation + ' ?x1. '
                                  """
    }
    """)
    # # print(query)
    sparql.setQuery(query)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query)
        exit(0)
    rtn = []
    for result in results['results']['bindings']:
        rtn.append((result['x0']['value'].replace('http://rdf.freebase.com/ns/', ''), result['x1']['value']))

    return rtn


def get_types(entity: str) -> List[str]:
    query = ("""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX : <http://rdf.freebase.com/ns/> 
    SELECT (?x0 AS ?value) WHERE {
    SELECT DISTINCT ?x0  WHERE {
    """
             ':' + entity + ' :type.object.type ?x0 . '
                            """
    }
    }
    """)
    # print(query)
    sparql.setQuery(query)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query)
        exit(0)
    rtn = []
    for result in results['results']['bindings']:
        rtn.append(result['value']['value'].replace('http://rdf.freebase.com/ns/', ''))

    return rtn

def get_notable_type(entity: str):
    query = ("""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX : <http://rdf.freebase.com/ns/> 
        SELECT (?x0 AS ?value) WHERE {
        SELECT DISTINCT ?x0  WHERE {
        
        """
             ':' + entity + ' :common.topic.notable_types ?y . '
                            """
        ?y :type.object.name ?x0
        FILTER (lang(?x0) = 'en')
    }
    }
    """)

    # print(query)
    sparql.setQuery(query)
    results = sparql.query().convert()
    rtn = []
    for result in results['results']['bindings']:
        rtn.append(result['value']['value'])

    if len(rtn) == 0:
        rtn = ['entity']

    return rtn


def get_friendly_name(entity: str) -> str:
    query = ("""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX : <http://rdf.freebase.com/ns/> 
    SELECT (?x0 AS ?value) WHERE {
    SELECT DISTINCT ?x0  WHERE {
    """
             ':' + entity + ' :type.object.name ?x0 . '
                            """
    }
    }
    """)
    # # print(query)
    sparql.setQuery(query)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query)
        exit(0)
    rtn = []
    for result in results['results']['bindings']:
        if result['value']['xml:lang'] == 'en':
            rtn.append(result['value']['value'])

    if len(rtn) == 0:
        query = ("""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX : <http://rdf.freebase.com/ns/> 
        SELECT (?x0 AS ?value) WHERE {
        SELECT DISTINCT ?x0  WHERE {
        """
                 ':' + entity + ' :common.topic.alias ?x0 . '
                                """
        }
        }
        """)
        # # print(query)
        sparql.setQuery(query)
        try:
            results = sparql.query().convert()
        except urllib.error.URLError:
            print(query)
            exit(0)
        for result in results['results']['bindings']:
            if result['value']['xml:lang'] == 'en':
                rtn.append(result['value']['value'])

    if len(rtn) == 0:
        return 'null'

    return rtn[0]


def get_degree(entity: str):
    degree = 0

    query1 = ("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX : <http://rdf.freebase.com/ns/> 
            SELECT count(?x0) as ?value WHERE {
            """
              '?x1 ?x0 ' + ':' + entity + '. '
                                          """
     FILTER regex(?x0, "http://rdf.freebase.com/ns/")
     }
     """)
    sparql.setQuery(query1)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query1)
        exit(0)
    for result in results['results']['bindings']:
        degree += int(result['value']['value'])

    query2 = ("""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX : <http://rdf.freebase.com/ns/> 
        SELECT count(?x0) as ?value WHERE {
        """
              ':' + entity + ' ?x0 ?x1 . '
                             """
    FILTER regex(?x0, "http://rdf.freebase.com/ns/")
    }
    """)

    sparql.setQuery(query2)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query2)
        exit(0)
    for result in results['results']['bindings']:
        degree += int(result['value']['value'])

    return degree


def get_in_attributes(value: str):
    in_attributes = set()

    query1 = ("""
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX : <http://rdf.freebase.com/ns/> 
                SELECT (?x0 AS ?value) WHERE {
                SELECT DISTINCT ?x0  WHERE {
                """
              '?x1 ?x0 ' + value + '. '
                                   """
    FILTER regex(?x0, "http://rdf.freebase.com/ns/")
    }
    }
    """)
    # print(query1)

    sparql.setQuery(query1)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query1)
        exit(0)
    for result in results['results']['bindings']:
        in_attributes.add(result['value']['value'].replace('http://rdf.freebase.com/ns/', ''))

    return in_attributes


def get_in_relations(entity: str):
    in_relations = set()

    query1 = ("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX : <http://rdf.freebase.com/ns/> 
            SELECT (?x0 AS ?value) WHERE {
            SELECT DISTINCT ?x0  WHERE {
            """
              '?x1 ?x0 ' + ':' + entity + '. '
                                          """
     FILTER regex(?x0, "http://rdf.freebase.com/ns/")
     }
     }
     """)
    # print(query1)

    sparql.setQuery(query1)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query1)
        exit(0)
    for result in results['results']['bindings']:
        in_relations.add(result['value']['value'].replace('http://rdf.freebase.com/ns/', ''))

    return in_relations


def get_in_entities(entity: str, relation: str):
    neighbors = set()

    query1 = ("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX : <http://rdf.freebase.com/ns/> 
            SELECT (?x1 AS ?value) WHERE {
            SELECT DISTINCT ?x1  WHERE {
            """
              '?x1' + ':' + relation + ':' + entity + '. '
                                                      """
                 FILTER regex(?x1, "http://rdf.freebase.com/ns/")
                 }
                 }
                 """)
    # print(query1)

    sparql.setQuery(query1)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query1)
        exit(0)
    for result in results['results']['bindings']:
        neighbors.add(result['value']['value'].replace('http://rdf.freebase.com/ns/', ''))

    return neighbors


def get_in_entities_for_literal(value: str, relation: str):
    neighbors = set()

    query1 = ("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX : <http://rdf.freebase.com/ns/> 
            SELECT (?x1 AS ?value) WHERE {
            SELECT DISTINCT ?x1  WHERE {
            """
              '?x1' + ':' + relation + ' ' + value + '. '
                                                     """
                FILTER regex(?x1, "http://rdf.freebase.com/ns/")
                }
                }
                """)
    # print(query1)

    sparql.setQuery(query1)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query1)
        exit(0)
    for result in results['results']['bindings']:
        neighbors.add(result['value']['value'].replace('http://rdf.freebase.com/ns/', ''))

    return neighbors


def get_in_entities_for_operator_literal(value: str, dtype: str, operator: str, relation: str):
    neighbors = set()

    query1 = ("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX : <http://rdf.freebase.com/ns/>
            SELECT (?x1 AS ?value) WHERE {
            SELECT DISTINCT ?x1  WHERE {
            """
              '?x1' + ':' + relation + ' ?x2.' 
                                                """

                FILTER regex(?x1, "http://rdf.freebase.com/ns/")
                FILTER (?x2 """ + operator + " "  + "\""+ value + "\""+ "^^<"+ dtype + """>) 
                }
                }
                """)
    # print(query1)

    sparql.setQuery(query1)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query1)
        exit(0)
    for result in results['results']['bindings']:
        neighbors.add(result['value']['value'].replace('http://rdf.freebase.com/ns/', ''))

    return neighbors

def get_out_relations(entity: str):
    out_relations = set()

    query2 = ("""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX : <http://rdf.freebase.com/ns/> 
        SELECT (?x0 AS ?value) WHERE {
        SELECT DISTINCT ?x0  WHERE {
        """
              ':' + entity + ' ?x0 ?x1 . '
                             """
    FILTER regex(?x0, "http://rdf.freebase.com/ns/")
    }
    }
    """)
    # print(query2)

    sparql.setQuery(query2)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query2)
        exit(0)
    for result in results['results']['bindings']:
        out_relations.add(result['value']['value'].replace('http://rdf.freebase.com/ns/', ''))

    return out_relations


def get_out_entities(entity: str, relation: str):
    neighbors = set()

    query2 = ("""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX : <http://rdf.freebase.com/ns/> 
        SELECT (?x1 AS ?value) WHERE {
        SELECT DISTINCT ?x1  WHERE {
        """
              ':' + entity + ':' + relation + ' ?x1 . '
                                              """
                     FILTER regex(?x1, "http://rdf.freebase.com/ns/")
                     }
                     }
                     """)
    # print(query2)

    sparql.setQuery(query2)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query2)
        exit(0)
    for result in results['results']['bindings']:
        neighbors.add(result['value']['value'].replace('http://rdf.freebase.com/ns/', ''))

    return neighbors

def get_out_entities_literal(entity: str, relation: str):
    neighbors = set()

    query2 = ("""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX : <http://rdf.freebase.com/ns/> 
        SELECT (?x1 AS ?value) WHERE {
        SELECT DISTINCT ?x1  WHERE {
        """
              ':' + entity + ':' + relation + ' ?x1 . '
                                              """
                     }
                     }
                     """)
    # print(query2)

    sparql.setQuery(query2)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query2)
        exit(0)
    for result in results['results']['bindings']:
        neighbors.add(result['value']['value'].replace('http://rdf.freebase.com/ns/', ''))

    return neighbors


def get_entities_cmp(value, relation: str, cmp: str):
    neighbors = set()

    query2 = ("""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX : <http://rdf.freebase.com/ns/> 
        SELECT (?x1 AS ?value) WHERE {
        SELECT DISTINCT ?x1  WHERE {
        """
              '?x1' + ':' + relation + ' ?sk0 . '
                                       """
              FILTER regex(?x1, "http://rdf.freebase.com/ns/")
              """
                                       f'FILTER (?sk0 {cmp} {value})'
                                       """
                                       }
                                       }
                                       """)
    # print(query2)

    sparql.setQuery(query2)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query2)
        exit(0)
    for result in results['results']['bindings']:
        neighbors.add(result['value']['value'].replace('http://rdf.freebase.com/ns/', ''))

    return neighbors


def get_adjacent_relations(entity: str):
    in_relations = set()
    out_relations = set()

    query1 = ("""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX : <http://rdf.freebase.com/ns/> 
        SELECT (?x0 AS ?value) WHERE {
        SELECT DISTINCT ?x0  WHERE {
        """
              '?x1 ?x0 ' + ':' + entity + '. '
                                          """
     FILTER regex(?x0, "http://rdf.freebase.com/ns/")
     }
     }
     """)

    sparql.setQuery(query1)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query1)
        exit(0)
    for result in results['results']['bindings']:
        in_relations.add(result['value']['value'].replace('http://rdf.freebase.com/ns/', ''))

    query2 = ("""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX : <http://rdf.freebase.com/ns/> 
    SELECT (?x0 AS ?value) WHERE {
    SELECT DISTINCT ?x0  WHERE {
    """
              ':' + entity + ' ?x0 ?x1 . '
                             """
    FILTER regex(?x0, "http://rdf.freebase.com/ns/")
    }
    }
    """)

    sparql.setQuery(query2)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query2)
        exit(0)
    for result in results['results']['bindings']:
        out_relations.add(result['value']['value'].replace('http://rdf.freebase.com/ns/', ''))

    return in_relations, out_relations


def get_adjacent_relations_data(entity: str):
    in_relations = set()
    out_relations = set()
    data_path = set()
    paths_dict = {}
    data_path_dict = {}

    query1 = ("""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX : <http://rdf.freebase.com/ns/> 
        SELECT ?x1,?x0 WHERE {
        SELECT DISTINCT ?x1,?x0  WHERE {
        """
              '?x1 ?x0 ' + ':' + entity + '. '
                                          """
     FILTER regex(?x0, "http://rdf.freebase.com/ns/")
     }
     }
     """)

    sparql.setQuery(query1)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query1)
        exit(0)
    
    local_data_path = set() 
    for result in results['results']['bindings']:
        tup = []
        for var in result:
            tup.append(result[var]['value'].replace('http://rdf.freebase.com/ns/', ''))
        tup.append(entity)
        in_relations.add(tup[1])
        data_path.add(tuple(tup))
        local_data_path.add(tuple(tup))
    
    paths_dict['q1'] = list(in_relations)
    data_path_dict['q1'] = list(local_data_path)

    query2 = ("""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX : <http://rdf.freebase.com/ns/> 
    SELECT ?x0,?x1 WHERE {
    SELECT DISTINCT ?x0,?x1  WHERE {
    """
              ':' + entity + ' ?x0 ?x1 . '
                             """
    FILTER regex(?x0, "http://rdf.freebase.com/ns/")
    }
    }
    """)

    sparql.setQuery(query2)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query2)
        exit(0)

    local_data_path = set()
    for result in results['results']['bindings']:
        tup = []
        tup.append(entity)
        for var in result:
            tup.append(result[var]['value'].replace('http://rdf.freebase.com/ns/', ''))
        out_relations.add(tup[1])
        data_path.add(tuple(tup))
        local_data_path.add(tuple(tup))

    paths_dict['q2'] = list(out_relations)
    data_path_dict['q2'] = list(local_data_path)
    return in_relations, out_relations, data_path, paths_dict, data_path_dict


def get_2hop_relations_from_2entities(entity0: str, entity1: str):  # m.027lnzs  m.0zd6  3200017000000
    query = ("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX : <http://rdf.freebase.com/ns/>
            SELECT distinct ?x0 as ?r0 ?y as ?r1 WHERE {
            """
             '?x1 ?x0 ' + ':' + entity0 + ' .\n' + '?x1 ?y ' + ':' + entity1 + ' .'
                                                                               """
                                                       FILTER regex(?x0, "http://rdf.freebase.com/ns/")
                                                       FILTER regex(?y, "http://rdf.freebase.com/ns/")
                                                       }
                                                       """)
    # print(query)
    pass

roles = []
def get_2hop_relations(entity: str):
    in_relations = set()
    out_relations = set()
    paths = []

    query1 = ("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX : <http://rdf.freebase.com/ns/>
            SELECT distinct ?x0 as ?r0 ?y as ?r1 WHERE {
            """
              '?x1 ?x0 ' + ':' + entity + '. '
                                          """
                ?x2 ?y ?x1 .
                  FILTER regex(?x0, "http://rdf.freebase.com/ns/")
                  FILTER regex(?y, "http://rdf.freebase.com/ns/")
                  }
                  """)

    sparql.setQuery(query1)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query1)
        exit(0)
    for result in results['results']['bindings']:
        r1 = result['r1']['value'].replace('http://rdf.freebase.com/ns/', '')
        r0 = result['r0']['value'].replace('http://rdf.freebase.com/ns/', '')
        in_relations.add(r0)
        in_relations.add(r1)

        if r0 in roles and r1 in roles:
            paths.append((r0, r1))

    query2 = ("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX : <http://rdf.freebase.com/ns/> 
            SELECT distinct ?x0 as ?r0 ?y as ?r1 WHERE {
            """
              '?x1 ?x0 ' + ':' + entity + '. '
                                          """
                ?x1 ?y ?x2 .
                  FILTER regex(?x0, "http://rdf.freebase.com/ns/")
                  FILTER regex(?y, "http://rdf.freebase.com/ns/")
                  }
                  """)

    sparql.setQuery(query2)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query2)
        exit(0)
    for result in results['results']['bindings']:
        r1 = result['r1']['value'].replace('http://rdf.freebase.com/ns/', '')
        r0 = result['r0']['value'].replace('http://rdf.freebase.com/ns/', '')
        out_relations.add(r1)
        in_relations.add(r0)

        if r0 in roles and r1 in roles:
            paths.append((r0, r1 + '#R'))

    query3 = ("""
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX : <http://rdf.freebase.com/ns/>
                SELECT distinct ?x0 as ?r0 ?y as ?r1 WHERE {
                """
              ':' + entity + ' ?x0 ?x1 . '
                             """
                ?x2 ?y ?x1 .
                  FILTER regex(?x0, "http://rdf.freebase.com/ns/")
                  FILTER regex(?y, "http://rdf.freebase.com/ns/")
                  }
                  """)

    sparql.setQuery(query3)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query3)
        exit(0)
    for result in results['results']['bindings']:
        r1 = result['r1']['value'].replace('http://rdf.freebase.com/ns/', '')
        r0 = result['r0']['value'].replace('http://rdf.freebase.com/ns/', '')
        in_relations.add(r1)
        out_relations.add(r0)

        if r0 in roles and r1 in roles:
            paths.append((r0 + '#R', r1))

    query4 = ("""
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX : <http://rdf.freebase.com/ns/>
                SELECT distinct ?x0 as ?r0 ?y as ?r1 WHERE {
                """
              ':' + entity + ' ?x0 ?x1 . '
                             """
                ?x1 ?y ?x2 .
                  FILTER regex(?x0, "http://rdf.freebase.com/ns/")
                  FILTER regex(?y, "http://rdf.freebase.com/ns/")
                  }
                  """)

    sparql.setQuery(query4)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query4)
        exit(0)
    for result in results['results']['bindings']:
        r1 = result['r1']['value'].replace('http://rdf.freebase.com/ns/', '')
        r0 = result['r0']['value'].replace('http://rdf.freebase.com/ns/', '')
        out_relations.add(r1)
        out_relations.add(r0)

        if r0 in roles and r1 in roles:
            paths.append((r0 + '#R', r1 + '#R'))

    return in_relations, out_relations, paths


def get_2hop_relations_data(entity: str):
    in_relations = set()
    out_relations = set()
    paths = set()
    data_path = []
    paths_dict = {}
    data_path_dict = {}

    query1 = ("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX : <http://rdf.freebase.com/ns/>
            SELECT distinct ?x2, ?y, ?x1, ?x0 WHERE {
            """
              '?x1 ?x0 ' + ':' + entity + '. '
                                          """
                ?x2 ?y ?x1 .
                  FILTER regex(?x0, "http://rdf.freebase.com/ns/")
                  FILTER regex(?y, "http://rdf.freebase.com/ns/")
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/common.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/type.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/kg.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/user.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/base.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/dataworld')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/freebase')))
                  

                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/common.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/type.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/kg.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/user.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/base.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/dataworld')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/freebase')))
                  }
                  """)

    sparql.setQuery(query1)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query1)
        exit(0)
    local_path = set()
    local_data_path = set()
    for result in results['results']['bindings']:
        r1 = result['y']['value'].replace('http://rdf.freebase.com/ns/', '')
        r0 = result['x0']['value'].replace('http://rdf.freebase.com/ns/', '')
        x1 = result['x1']['value'].replace('http://rdf.freebase.com/ns/', '')
        x2 = result['x2']['value'].replace('http://rdf.freebase.com/ns/', '')
        in_relations.add(r0)
        in_relations.add(r1)

        if r0 in roles and r1 in roles:
            paths.add((r0, r1))
            data_path.append((x1, r0, entity, x2, r1, x1))
            local_path.add((r0, r1))
            local_data_path.add((x1, r0, entity, x2, r1, x1))

    paths_dict['q1'] = list(local_path)
    data_path_dict['q1'] = list(local_data_path)

    query2 = ("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX : <http://rdf.freebase.com/ns/> 
            SELECT distinct ?x2, ?y, ?x1, ?x0 WHERE {
            """
              '?x1 ?x0 ' + ':' + entity + '. '
                                          """
                ?x1 ?y ?x2 .
                  FILTER regex(?x0, "http://rdf.freebase.com/ns/")
                  FILTER regex(?y, "http://rdf.freebase.com/ns/")
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/common.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/type.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/kg.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/user.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/base.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/dataworld')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/freebase')))
                  

                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/common.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/type.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/kg.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/user.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/base.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/dataworld')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/freebase')))
                  }
                  """)

    sparql.setQuery(query2)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query2)
        exit(0)
    local_path = set()
    local_data_path = set()
    for result in results['results']['bindings']:
        r1 = result['y']['value'].replace('http://rdf.freebase.com/ns/', '')
        r0 = result['x0']['value'].replace('http://rdf.freebase.com/ns/', '')
        x1 = result['x1']['value'].replace('http://rdf.freebase.com/ns/', '')
        x2 = result['x2']['value'].replace('http://rdf.freebase.com/ns/', '')
        out_relations.add(r1)
        in_relations.add(r0)

        if r0 in roles and r1 in roles:
            paths.add((r0, r1 + '#R'))
            data_path.append((x1, r0, entity, x1, r1, x2))
            local_path.add((r0, r1 + '#R'))
            local_data_path.add((x1, r0, entity, x1, r1, x2))

    paths_dict['q2'] = list(local_path)
    data_path_dict['q2'] = list(local_data_path)

    query3 = ("""
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX : <http://rdf.freebase.com/ns/>
                SELECT distinct ?x2, ?y, ?x1, ?x0 WHERE {
                """
              ':' + entity + ' ?x0 ?x1 . '
                             """
                ?x2 ?y ?x1 .
                  FILTER regex(?x0, "http://rdf.freebase.com/ns/")
                  FILTER regex(?y, "http://rdf.freebase.com/ns/")
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/common.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/type.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/kg.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/user.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/base.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/dataworld')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/freebase')))
                  

                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/common.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/type.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/kg.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/user.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/base.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/dataworld')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/freebase')))
                  }
                  """)

    sparql.setQuery(query3)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query3)
        exit(0)
    local_path = set()
    local_data_path = set()
    for result in results['results']['bindings']:
        r1 = result['y']['value'].replace('http://rdf.freebase.com/ns/', '')
        r0 = result['x0']['value'].replace('http://rdf.freebase.com/ns/', '')
        x1 = result['x1']['value'].replace('http://rdf.freebase.com/ns/', '')
        x2 = result['x2']['value'].replace('http://rdf.freebase.com/ns/', '')
        in_relations.add(r1)
        out_relations.add(r0)

        if r0 in roles and r1 in roles:
            paths.add((r0 + '#R', r1))
            data_path.append((entity, r0, x1, x2, r1, x1))
            local_path.add((r0 + '#R', r1))
            local_data_path.add((entity, r0, x1, x2, r1, x1))

    paths_dict['q3'] = list(local_path)
    data_path_dict['q3'] = list(local_data_path)

    query4 = ("""
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX : <http://rdf.freebase.com/ns/>
                SELECT distinct ?x2, ?y, ?x1, ?x0 WHERE {
                """
              ':' + entity + ' ?x0 ?x1 . '
                             """
                ?x1 ?y ?x2 .
                  FILTER regex(?x0, "http://rdf.freebase.com/ns/")
                  FILTER regex(?y, "http://rdf.freebase.com/ns/")
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/common.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/type.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/kg.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/user.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/base.')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/dataworld')))
                  FILTER (!(strstarts(str(?x0), 'http://rdf.freebase.com/ns/freebase')))
                  

                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/common.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/type.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/kg.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/user.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/base.')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/dataworld')))
                  FILTER (!(strstarts(str(?y), 'http://rdf.freebase.com/ns/freebase')))
                  }
                  """)

    sparql.setQuery(query4)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query4)
        exit(0)
    local_path = set()
    local_data_path = set()
    for result in results['results']['bindings']:
        r1 = result['y']['value'].replace('http://rdf.freebase.com/ns/', '')
        r0 = result['x0']['value'].replace('http://rdf.freebase.com/ns/', '')
        x1 = result['x1']['value'].replace('http://rdf.freebase.com/ns/', '')
        x2 = result['x2']['value'].replace('http://rdf.freebase.com/ns/', '')
        out_relations.add(r1)
        out_relations.add(r0)

        if r0 in roles and r1 in roles:
            paths.add((r0 + '#R', r1 + '#R'))
            data_path.append((entity, r0, x1, x1, r1, x2))
            local_path.add((r0 + '#R', r1 + '#R'))
            local_data_path.add((entity, r0, x1, x1, r1, x2))

    paths_dict['q4'] = list(local_path)
    data_path_dict['q4'] = list(local_data_path)

    return in_relations, out_relations, paths, data_path, paths_dict, data_path_dict


def get_label(entity: str) -> str:
    query = ("""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX : <http://rdf.freebase.com/ns/> 
        SELECT (?x0 AS ?label) WHERE {
        SELECT DISTINCT ?x0  WHERE {
        """
             ':' + entity + ' rdfs:label ?x0 . '
                            """
                            FILTER (langMatches( lang(?x0), "EN" ) )
                             }
                             }
                             """)
    # # print(query)
    sparql.setQuery(query)
    try:
        results = sparql.query().convert()
    except urllib.error.URLError:
        print(query)
        exit(0)
    rtn = []
    for result in results['results']['bindings']:
        label = result['label']['value']
        rtn.append(label)
    if len(rtn) != 0:
        return rtn[0]
    else:
        return None



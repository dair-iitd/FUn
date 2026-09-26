import openai
import json
from logic_form_util import lisp_to_sparql
import time
import os
import urllib
from SPARQLWrapper import SPARQLWrapper, JSON
from SPARQLWrapper.SPARQLExceptions import QueryBadFormed
from sklearn.metrics import f1_score, precision_score, recall_score
import my_secrets
import logging 
from sparql_typechk import check_type
from typing import List, Tuple
# from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter
logger = logging.getLogger(__name__)
from api_keys import key
import datetime


HEADER = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> 
PREFIX : <http://rdf.freebase.com/ns/> 
PREFIX ns: <http://rdf.freebase.com/ns/>
"""

# sparql = SPARQLWrapper("http://10.237.23.161:3001/sparql")
# sparql = SPARQLWrapper("http://10.237.23.185:3001/sparql")
import os
# sparql url
hostname = os.environ['HOSTNAME']
freebase_addr=f'e{hostname}.hpc.iitd.ac.in'

sparql = SPARQLWrapper(f"http://e{hostname}.hpc.iitd.ac.in:3001/sparql")
# sparql = SPARQLWrapper("http://10.237.23.124:3001/sparql")      #lab system new ip

sparql.setTimeout(200)
sparql.setReturnFormat(JSON)

HTTP_PROXY = 'http://10.10.78.61:3128'
HTTPS_PROXY = 'http://10.10.78.61:3128'

HTTP_PROXY = 'http://10.10.88.6:3128'
HTTPS_PROXY = 'http://10.10.88.6:3128'

MODE = 'azure'

#TODO: pls uncomment this!!!
REVERSE_PROPERTIES_FILE = '../data/freebase/reverse_properties.txt'
reverse_properties_dict = {}
with open(REVERSE_PROPERTIES_FILE) as f:
    reverse_properties = f.readlines()
    for reverse_property in reverse_properties:
        reverse_property_line = reverse_property.strip()
        reverse_property_line = reverse_property.split()
        p1 = reverse_property_line[0]
        p2 = reverse_property_line[-1]
        reverse_properties_dict[p1] = p2
        reverse_properties_dict[p2] = p1

FB_ROLES_FILE = '../data/freebase/fb_roles.txt'
fb_roles_dict = {}
with open(FB_ROLES_FILE) as f:
    fb_roles = f.readlines()
    for fb_role in fb_roles:
        fb_role_line = fb_role.strip()
        fb_role_line = fb_role.split()
        t1 = fb_role_line[0]
        t2 = fb_role_line[2]
        rel = fb_role_line[1]
        fb_roles_dict[rel] = f'{rel} (type:{t1} R type:{t2})'

def execute_query(query: str, syntax_feedback: bool = False, cnt: int=0) -> List[str]:
    #TODO: Strict checking of void variables
    if(query == 'error'):
        logging.info('youre trying to execute an error! pls recheck')
        return []
    query= query.strip()
    if not query.startswith('PREFIX'):
        query = HEADER + query
    sparql.setQuery(query)
    try:
        results = sparql.query().convert()
        return results
    except urllib.error.URLError as e:
        logging.info(f'oof! error encontered: {e}')
        logging.info(query)
        # exit(0)
        return []
    except TimeoutError:
        logging.info('oof! time limit exceeded')
        logging.info(query)
        return []
    except Exception as e:
        if cnt>0 or not syntax_feedback:
            return ['syntax_error']
        logging.info(f'oof! error encontered: {e}')
        logging.info(f'count: {cnt}')
        logging.info(query)
        new_query = correct_syntax(query, e)
        return execute_query(new_query, syntax_feedback, cnt+1)

def get_common_name(mid_url: str):
    if not mid_url.startswith('http://'):
        if not mid_url.startswith('m.'):
            return mid_url
        mid_url = "http://rdf.freebase.com/ns/" + mid_url
    try:
        query = "SELECT ?name WHERE {\
                <" + mid_url + "> <http://rdf.freebase.com/ns/type.object.name> ?name .\
                    FILTER(LANG(?name) = \"en\")\
                }"
        results = execute_query(query)
        return results['results']['bindings'][0]['name']['value']
    except:
        try:
            type_query = "SELECT ?type WHERE {\
                            <"+mid_url+"> a ?type .\
                        }"
            type = execute_query(type_query)
            return "type: " + type['results']['bindings'][0]['type']['value'].split('/')[-1]
        except:
            return mid_url


def is_type_node(mid_list: List[str]) -> bool:
    for mid in mid_list:
        if mid.startswith('g.'):
            continue
        common_name = get_common_name(mid)
        if common_name.startswith('type:'):
            logging.info('cvt node detected')
            return True
    return False


def load_json(fname: str):
    with open(fname) as f:
        return json.load(f)

def dump_json(obj, fname, indent=4):
    with open(fname, 'w') as f:
        return json.dump(obj, f, indent=indent)

def simplify_cand_paths(cand_paths_str: str, list_of_rels: List[str]) -> str:
    '''
    convert the candidate paths into a shorter version
    by removing the prefixes and filters
    '''
    cand_paths = cand_paths_str.split(' | ')
    new_cand_paths = []
    for cand_path in cand_paths:
        lines = cand_path.split('\n')
        # print(lines)
        new_lines = []
        for line in lines:
            if line.startswith('PREFIX'):
                continue
            elif line.startswith('FILTER'):
                continue
            if line.endswith('.'):
                line_rdf = line.split(' ')
                rel = line_rdf[1].split('ns:')[-1]
                # print(rel)
                if (rel not in list_of_rels) and (rel in reverse_properties_dict):
                    rev_rel = reverse_properties_dict[rel]
                    if rev_rel in list_of_rels:
                        line_rdf[1] = f'ns:{rev_rel}'
                        line_rdf[0], line_rdf[2] = line_rdf[2], line_rdf[0]
                        line = (' ').join(line_rdf)
            new_lines.append(line)
        new_cand_path = ('\n').join(new_lines)
        new_cand_paths.append(new_cand_path)
    # new_cand_paths = list(set(new_cand_paths)) # keeping only unique occurences
    # just corrected!!! big big bug :(
    # print(new_cand_paths)
    new_cand_paths_updated = []
    for new_cand_path in new_cand_paths: 
        if new_cand_path not in new_cand_paths_updated: 
            new_cand_paths_updated.append(new_cand_path)
    new_cand_paths = new_cand_paths_updated 
    # correction ends

    new_cand_paths_str = (' | ').join(new_cand_paths)
    return new_cand_paths_str

def simplify_cand_rels(cand_rels_str: str) -> Tuple[str, List[str]]:
    '''
    simplify candidate rels by removing reverse relns and
    mentioning the types of the rels
    '''
    cand_rels = cand_rels_str.split('|')
    new_cand_rels = []
    list_of_rels = []
    for cand_rel in cand_rels:
        if cand_rel in new_cand_rels:
            continue
        # elif cand_rel in reverse_properties_dict:
        #     if reverse_properties_dict[cand_rel] in list_of_rels:
        #         continue
        if cand_rel in fb_roles_dict:
            new_cand_rels.append(fb_roles_dict[cand_rel])
        else:
            new_cand_rels.append(f'{cand_rel} (type: R type:)')
        list_of_rels.append(cand_rel)
    new_cand_rels_str = ('|').join(new_cand_rels)
    return (new_cand_rels_str, list_of_rels)
    
def process_retriever_op(retrieved_data: str) -> Tuple[str, str, str, str, str]:
    '''
    process the retrieved data from the retriever
    returns ques, entities, classes, paths, relns
    '''
    cand_rels = retrieved_data.split('|relation|')[1]
    retrieved_data = retrieved_data.split('|relation|')[0]
    cand_classes = retrieved_data.split('|class|')[1]
    retrieved_data = retrieved_data.split('|class|')[0]
    if '|entity|' in retrieved_data:
        cand_entities = retrieved_data.split('|entity|')[1]
        retrieved_data = retrieved_data.split('|entity|')[0]
    else:
        cand_entities = ''
    if '|query|' in retrieved_data:
        cand_paths = retrieved_data.split('|query|')[1]
        retrieved_data = retrieved_data.split('|query|')[0]
    else:
        cand_paths = ''
    ques = retrieved_data
    return ques, cand_entities, cand_classes, cand_paths, cand_rels

def get_topic_entity_mids(retriever_data: str) -> List[str]:
    ques, cand_entities, cand_classes, cand_paths, cand_rels = process_retriever_op(retriever_data)
    cand_entities_list = (cand_entities).split('|')
    for i in range(len(cand_entities_list)):
        cand_entities_list[i] = cand_entities_list[i].strip().split(' ')[-1]
    return cand_entities_list

def extract_rels_ents(sparql: str) -> Tuple[List[str], List[str]]:
    '''
    extract rels  & entities from a sparql query
    '''
    sparql = sparql.replace('PREFIX', '\nPREFIX')
    sparql = sparql.replace('(', ' ( ')
    sparql = sparql.replace(')', ' ) ')
    sparql = sparql.replace('<http://rdf.freebase.com/ns/>', ':')
    lines = sparql.split('\n')
    rels = []
    ents = []
    for line in lines:
        if line.startswith('PREFIX'):
            continue
        words = line.split()
        for word in words:
            if ':' not in word:
                continue 
            if 'xsd' in word:
                continue           
            dctr = word.count('.')
            if not dctr and (word != 'rdfs:label'):
                continue
            processed_word = word.split(':')[-1]
            if (dctr == 1) and (processed_word.startswith('m.') or processed_word.startswith('g.')):
                ents.append(processed_word)
            else:
                rels.append(processed_word)
    return list(set(rels)), list(set(ents))
            
def check_retriever_correctness(cand_entites: str, cand_classes: str, cand_paths: str, cand_rels: str, gt_program: str) -> bool:
    '''
    given the retrieved components, is it possible to generate gt program?
    '''
    # step1: extract cand_rels from cand_paths
    # cand_rels += type.object.type
    # cand_rels += cand_classes
    list_of_cand_rels = cand_rels.split('|')
    list_of_cand_rels += cand_classes.split('|')
    list_of_cand_rels += ['type.object.type']
    list_of_cand_paths = cand_paths.split('|')
    
    for cand_path in list_of_cand_paths:
        list_of_cand_rels += extract_rels_ents(sexp_to_sparql(cand_path))[0]
    actual_rels, actual_ents = extract_rels_ents(gt_program)
    cand_entites = [cand.split(' ')[-1] for cand in cand_entites.split('|')]
    for ent in actual_ents:
        if ent not in cand_entites:
            # logging.info(f'{ent} is missing from the retrieved entities')
            return False
    for rel in actual_rels:
        if rel not in list_of_cand_rels:
            # logging.info(f'{rel} is missing from the retrieved rels')
            return False
    return True

def get_retriever_correctness(cand_entites: str, cand_classes: str, cand_paths: str, cand_rels: str, gt_program: str) -> str:
    '''
    given the retrieved components (entities & relations), is it possible to generate gt program?
    if yes, we return 'correct',
    if not, we return whatever is missing
    '''
    # step1: extract cand_rels from cand_paths
    # cand_rels += type.object.type
    # cand_rels += cand_classes
    cand_entites = cand_entites.strip()
    cand_classes = cand_classes.strip()
    cand_paths = cand_paths.strip()
    cand_rels = cand_rels.strip()

    list_of_cand_rels = cand_rels.split('|')
    list_of_cand_rels += cand_classes.split('|')
    list_of_cand_rels += ['type.object.type']
    list_of_cand_paths = cand_paths.split('|')
    
    for cand_path in list_of_cand_paths:
        list_of_cand_rels += extract_rels_ents(sexp_to_sparql(cand_path))[0]
    actual_rels, actual_ents = extract_rels_ents(gt_program)
    cand_entites = [cand.strip().split(' ')[-1] for cand in cand_entites.split('|')]
    for ent in actual_ents:
        if ent not in cand_entites:
            return (f'{ent} is NOT defined over this knowledge base')
    for rel in actual_rels:
        if rel not in list_of_cand_rels:
            return (f'{rel} is NOT a part of the schema.')
    return 'correct'

def get_answer(lf: str, syntax_feedback: bool = True)-> list:    
    if lf == 'NK':
        return []
    try:
        if 'http' not in lf and 'SELECT' not in lf:
            lf = lisp_to_sparql(lf)
    except:
        return ['nonsense']
        import ipdb; ipdb.set_trace()
    lf = lf.replace('`','')
    lf = lf.replace('ns:', ':')
    if 'SELECT' in lf:
        temp = lf.split('SELECT')
        # print(temp)
        lf = 'SELECT'.join(temp[1:])
        lf= 'SELECT'+lf
        
        temp = lf.split('}')
        # print(temp)
        lf = '}'.join(temp[:-1])
        lf= lf+'}'
        
    lf = lf.strip()


    query_result = execute_query(lf, syntax_feedback)
    try:
        varnames = query_result['head']['vars']
        if len(varnames) > 1:
            logger.info(f'Multiple variables being returned...')
            return ['multiple_vars']
        sampled_query_results = query_result['results']['bindings']
        varname = list(sampled_query_results[0].keys())[0]
        for i in range(len(sampled_query_results)):
            if varname not in sampled_query_results[i]:
                # this means multiple variables are being returned...
                logger.info(f'Multiple variables being returned...')
                return ['multiple_vars']
        logger.info(f'varname: {varname}')
        logger.info(f'sampled_query_results: {sampled_query_results}')
        answers = []
        for i in range(len(sampled_query_results)):
            answers.append(sampled_query_results[i][varname]['value'].split('http://rdf.freebase.com/ns/')[-1])
        return answers
    except:
        logging.info('WARNING: there was some issue in obtaining the answer')
        logging.info(f"query result: {query_result}")
        return []
    
def sexp_to_sparql(sexp_paths: str) -> str:
    sparql_paths_list = []
    for sexpr in sexp_paths.split("|"):
        try:
            if sexpr == 'NK':
                sparql = 'NK'
            else:
                sparql = lisp_to_sparql(sexpr)

        except:
            sparql = ""

        if sparql != "":
            sparql_paths_list.append(sparql)

    sparql_paths = " | ".join(sparql_paths_list)
    return sparql_paths


# def ask_gpt_anything(messages_list: List[dict],  model: str = 'gpt-4', max_retries: int = 10, temperature: float = 0)-> str:
#     openai.api_key = my_secrets.AZURE_OPENAI_KEY
#     openai.api_base = my_secrets.AZURE_OPENAI_ENDPOINT # your endpoint should look like the following https://YOUR_RESOURCE_NAME.openai.azure.com/
#     openai.api_type = 'azure'
#     openai.api_version = '2023-05-15' # this might change in the future
#     retries = 0
#     os.environ['http_proxy'] = HTTP_PROXY
#     os.environ['https_proxy'] = HTTPS_PROXY

#     if MODE == 'azure' and model == 'gpt-3.5-turbo':
#         model = 'gpt-35-turbo-0125'
#     stt = time.time()
#     logger.info('----asking gpt----')
#     logger.info(messages_list)
#     # logger.info(f"sys prompt: {sys_prompt}")
#     # logger.info(f"usr prompt: {usr_prompt}")
#     # logger.info(f"asst prompt: {asst_prompt}")
#     # messages_list = []
#     # if sys_prompt!= '':
#     #     messages_list.append({"role": "system", "content": sys_prompt})
#     # if usr_prompt != '':
#     #     messages_list.append({"role": "user", "content": usr_prompt})
#     # if asst_prompt != '':
#     #     messages_list.append({"role": "assistant", "content": asst_prompt})
#     while retries < max_retries:
#         try:
#             time.sleep(1)
#             client = openai.AzureOpenAI(
#                                     api_key=my_secrets.AZURE_OPENAI_KEY,  
#                                     api_version="2023-12-01-preview",
#                                     azure_endpoint = my_secrets.AZURE_OPENAI_ENDPOINT
#                                     )
#             completion = client.chat.completions.create(
#                 model = model, 
#                 temperature = temperature,
#                 messages=messages_list,
#                 seed=0
#             )
#             logging.info(f'gpt response: {completion.choices[0].message.content.strip()}')
#             ett = time.time()
#             logging.info(f'this gpt service took time: {ett-stt}')
#             return ((completion.choices[0].message.content.strip()))
#         except Exception as e:
#             logging.info(e)
#             print(e)
#             logging.info('timeout')
#             retries += 1
#             time.sleep(2*retries)
    
#     del os.environ['http_proxy'] 
#     del os.environ['https_proxy'] 


from contextlib import ExitStack
def create_batch_(qid, prompt):
    task = {
        "custom_id": str(qid),
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            # This is what you would have in your Chat Completions API call
            "model": 'gpt-4',
            "temperature": 0,
            "messages": prompt,
        }
        }
    return json.dumps(task)

def get_batch_job(client, id):
    batch_job = client.batches.retrieve(id)
    # print(batch_job)
    return batch_job

def get_result(client, batch_job):
    result_file_id = batch_job.output_file_id
    result = client.files.content(result_file_id).content
    line = json.loads(result)
    return line['response']['body']['choices'][0]['message']['content']

def ask_gpt_anything(messages_list: List[dict], model: str = 'gpt-4', max_retries: int = 30, temperature: float = 0) -> str:
    ret =  ask_gpt_anything_batch(messages_list, model, max_retries, temperature)

    # ret = ask_gpt_anything_direct(messages_list, model, max_retries, temperature)

    return ret
  

def ask_gpt_anything_batch(messages_list: List[dict], model: str = 'gpt-4', max_retries: int = 30, temperature: float = 0) -> str:
    # openai.api_key = my_secrets.AZURE_OPENAI_KEY
    # openai.api_base = my_secrets.AZURE_OPENAI_ENDPOINT
    # openai.api_type = 'azure'
    # openai.api_version = '2023-12-01-preview' # this might change in the future
    retries = 0

    if MODE == 'azure' and model == 'gpt-3.5-turbo':
        model = 'gpt-35-turbo-0125'
    model = 'gpt-4'
    with ExitStack() as stack:
        os.environ['http_proxy'] = HTTP_PROXY
        os.environ['https_proxy'] = HTTPS_PROXY
        stack.callback(lambda: os.environ.pop('http_proxy', None))
        stack.callback(lambda: os.environ.pop('https_proxy', None))

        if MODE == 'azure' and model == 'gpt-3.5-turbo':
            model = 'gpt-35-turbo-0125'
        stt = time.time()
        logger.info('----asking gpt----')
        logger.info(messages_list)

        # client = openai.AzureOpenAI(
        #     api_key=my_secrets.AZURE_OPENAI_KEY,  
        #     api_version="2023-12-01-preview",
        #     azure_endpoint=my_secrets.AZURE_OPENAI_ENDPOINT
        # )
        client = openai.OpenAI(
            api_key=my_secrets.key
        )
        
        cur_time= str(datetime.datetime.now()).replace(' ', '_')
        task_name = f'{cur_time}' 
        batch_tasks = [create_batch_('ask_gpt_anything', messages_list)]
        with open(f'./batch_runs/temp/{task_name}.jsonl', 'w') as file:
            file.write('\n'.join(batch_tasks))

        batch_file = client.files.create(
                                            file=open(f'./batch_runs/temp/{task_name}.jsonl', "rb"),
                                            purpose="batch"
                                            )      
        # print(batch_file) 

        batch_job = client.batches.create(
                                            input_file_id=batch_file.id,
                                            endpoint="/v1/chat/completions",
                                            completion_window="24h"
                                ) 
        
        while retries < max_retries:
            try:
                time.sleep(1)  # Sleep at the start of the loop to respect rate limits and back-off
                while(1):
                    # print(batch_job, batch_job.status)
                    batch_job = get_batch_job(client, batch_job.id)
                    if batch_job.status =="completed":
                        response = get_result(client, batch_job)
                        logging.info(f'gpt response: {response}')
                        ett = time.time()
                        logging.info(f'this gpt service took time: {ett-stt}')
                        client.close()
                        return response
                    elif batch_job.status =="failed":
                        break
                    else:
                        time.sleep(10)
            except Exception as e:
                logging.error(f'error on attempt {retries + 1}: {e}', exc_info=True)
                retries += 1
                time.sleep(4 * retries)  # Exponential back-off
    client.close()
    if retries>= max_retries:
        print("Not able to query chatgpt")
        print(response)
        raise Exception
    return "Failed to get response after retries"


def ask_gpt_anything_direct(messages_list: List[dict], model: str = 'gpt-4', max_retries: int = 30, temperature: float = 0) -> str:
    # openai.api_key = my_secrets.AZURE_OPENAI_KEY
    # openai.api_base = my_secrets.AZURE_OPENAI_ENDPOINT
    # openai.api_type = 'azure'
    # openai.api_version = '2023-12-01-preview' # this might change in the future
    retries = 0

    if MODE == 'azure' and model == 'gpt-3.5-turbo':
        model = 'gpt-35-turbo-0125'
    
    # model = 'gpt-4o-2024-08-06'

    with ExitStack() as stack:
        os.environ['http_proxy'] = HTTP_PROXY
        os.environ['https_proxy'] = HTTPS_PROXY
        stack.callback(lambda: os.environ.pop('http_proxy', None))
        stack.callback(lambda: os.environ.pop('https_proxy', None))

        if MODE == 'azure' and model == 'gpt-3.5-turbo':
            model = 'gpt-35-turbo-0125'
        stt = time.time()
        logger.info('----asking gpt----')
        logger.info(messages_list)

        # client = openai.AzureOpenAI(
        #     api_key=my_secrets.AZURE_OPENAI_KEY,  
        #     api_version="2023-12-01-preview",
        #     azure_endpoint=my_secrets.AZURE_OPENAI_ENDPOINT
        # )
        client = openai.OpenAI(
            api_key=my_secrets.key
        )
        
        while retries < max_retries:
            try:
                time.sleep(1)  # Sleep at the start of the loop to respect rate limits and back-off
                completion = client.chat.completions.create(
                    model=model, 
                    temperature=temperature,
                    messages=messages_list,
                    seed=0
                )
                response = completion.choices[0].message.content.strip()
                logging.info(f'gpt response: {response}')
                ett = time.time()
                logging.info(f'this gpt service took time: {ett-stt}')
                client.close()
                return response
            except Exception as e:
                logging.error(f'error on attempt {retries + 1}: {e}', exc_info=True)
                retries += 1
                time.sleep(4 * retries)  # Exponential back-off
    client.close()
    if retries>= max_retries:
        print("Not able to query chatgpt")
        print(response)
        raise Exception
    return "Failed to get response after retries"


def correct_syntax(query: str, exception: str) -> str:
    sys_prompt = 'Correct the syntax of the following sparql query. Return ONLY the corrected sparql query without any explanation'
    asst_prompt = query
    usr_prompt = str(exception)
    new_query = ask_gpt_anything([{"role": "system", "content": sys_prompt}, 
                                {"role": "assistant", "content": asst_prompt}, 
                                {"role": "user", "content": usr_prompt}])
    return new_query

def correct_syntax_prompt(query: str, exception: str) -> str:
    sys_prompt = 'Correct the syntax of the following sparql query. Return ONLY the corrected sparql query without any explanation'
    asst_prompt = query
    usr_prompt = str(exception)
    prompt = [{"role": "system", "content": sys_prompt}, 
                {"role": "assistant", "content": asst_prompt}, 
                {"role": "user", "content": usr_prompt}]
    return prompt

naturalize_varnames_cache = {}
def naturalize_varnames(sparql_query: str, syntax_feedback: bool = True)-> str:
    if sparql_query in naturalize_varnames_cache:
        return naturalize_varnames_cache[sparql_query]
    sys_prompt = 'change the sparql query to have variable names representative of what objects thet refer to. transform the variable names in this query. Do NOT change the prefix headers and relation names'
    usr_prompt = sparql_query
    prompt = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": usr_prompt}]
    new_sparql_query = ask_gpt_anything(prompt)
    old_ans = get_answer(sparql_query,syntax_feedback)
    new_ans = get_answer(new_sparql_query,syntax_feedback)
    if old_ans != new_ans:
        logger.info('WARNING: the new sparql query is not returning the same answer as the old one...returning old one')
        naturalize_varnames_cache[sparql_query] = sparql_query
        return sparql_query
    naturalize_varnames_cache[sparql_query] = new_sparql_query
    return new_sparql_query

def get_subset(data: List[dict], qid_list: List[str]) -> List[dict]:
    '''
    get the subset of data corresponding to the qids
    '''
    new_data = []
    for qn in data:
        if str(qn['qid']) in qid_list:
            new_data.append(qn)
    return new_data


def check_connected_ans_qn(pred_lf: str, syntax_feedback: bool = True)-> bool:
    '''
    checking whether the topic entity mid is connected to the answer node
    Assumption: the topic entity mid is mentioned by the 'VALUES' clause
    '''
    query = pred_lf
    query = query.replace('VALUES', '\nVALUES')
    new_query_l = []
    for line in query.split('\n'):
        if 'VALUES' not in line:
            new_query_l.append(line)
    new_query = '\n'.join(new_query_l)
    new_results = get_answer(new_query, syntax_feedback)
    old_results = get_answer(pred_lf, syntax_feedback)
    if new_results == old_results:
        return False
    else:
        return True
    


# ent_datas = json.load(open(json.load(open('config.json'))['input_test_file']))
# entities = {}
# #TODO: the prefix is 'ns:' in webqsp mode & ':' in grailqa mode...this needs to be generalized
# for data in ent_datas:
#     for node in data['graph_query']['nodes']:
#         if node['node_type'] == 'entity':
#             entities[':'+node['id']] = node['friendly_name']

def get_common_name(mid_url: str):
    if not mid_url.startswith('http://'):
        mid_url = "http://rdf.freebase.com/ns/" + mid_url
    try:
        query = "SELECT ?name WHERE {\
                <" + mid_url + "> <http://rdf.freebase.com/ns/type.object.name> ?name .\
                    FILTER(LANG(?name) = \"en\")\
                }"
        results = execute_query(query)
        return results['results']['bindings'][0]['name']['value']
    except:
        try:
            type_query = "SELECT ?type WHERE {\
                            <"+mid_url+"> a ?type .\
                        }"
            type = execute_query(type_query)
            return "type: " + type['results']['bindings'][0]['type']['value'].split('/')[-1]
        except:
            return mid_url



def mid_to_friendly(lf: str) -> str:
    '''
    replace mids with their friendly names
    '''
    lf = lf.replace('{', ' { ')
    lf = lf.replace('}', ' } ')
    words = lf.split()
    for idx, word in enumerate(words):
        if word.startswith('ns:'):
            word = word.replace('ns:', ':')
        if word.startswith(':m.') or word.startswith(':g.'):
            # if word in entities:
                # words[idx] = entities[word]
            words[idx] = get_common_name(word[1:])
    return ' '.join(words)


def naturalize_query(lf: str, syntax_feedback: bool = True)-> str:
    '''
    convert a logical form onto a natural language question
    '''
    #TODO: change entity mids to common names
    lf = lf.replace(' .', ' .\n')
    lf = lf.replace('-08:00', '')
    new_lines = []
    for line in lf.split('\n'):
        if 'FILTER' in line and ('!=' in line or 'langMatches' in line):
            continue
        new_lines.append(line)
    lf = ('\n').join(new_lines)
    lf = naturalize_varnames(lf, syntax_feedback)
    prompts = [
        {"role": "system", "content": "Convert this sparql query into a natural language question. Make the question as natural as possible. "},
        {"role": "user", "content": mid_to_friendly(lf)}
    ]

    # prompts = [
    #     {"role": "system", "content": "Convert this sparql query into a natural language question. Make the question as precise as possible, ensuring that the meaning of all relations as well as query operators(eg. UNION means question should have 'or' and not 'and') is clearly and correctly described. Do not use vague terms such as 'associated' or 'related to'. Try to follow the relation labels as provided as much as possible"},
    #     {"role": "user", "content": mid_to_friendly(lf)}
    # ]

    ret_prompt =  ask_gpt_anything(prompts, 'gpt-4')
    if 'associated' in ret_prompt: 
        #retrying once more to get rid of this ambiguity
        prompts_nota = [
            {"role": "system", "content": "Convert this sparql query into a natural language question. Make the question as natural as possible. Specify the relations clearly and avoid using words like 'associated'"},
            {"role": "user", "content": mid_to_friendly(lf)}
        ]
        ret_prompt =  ask_gpt_anything(prompts_nota, 'gpt-4')
    return ret_prompt

def get_explanation(pred_nl_qn: str, orig_nl_qn: str, are_same: bool)-> str: 
    '''
    given 2 nl qns, get explanation whether they are same or not
    '''
    if are_same:
        same_str = 'same'
    else:
        same_str = 'different'
    prompts = [
        {"role": "user", "content": f"Explain why the two questions \"{orig_nl_qn}\" and \"{pred_nl_qn}\" are {same_str}. If required, assume that the date today is August 10,2015"}
    ]
    return ask_gpt_anything(prompts, 'gpt-4')

def get_grounded(pred_lf: str, qid: str, retriever_augmented_test_data: List[dict])-> str:
    '''
    check if the logical form is grounded in the retrieved data
    if yes, return 'correct'
    if not, return whatever is missing
    '''
    retrieved_data = retriever_augmented_test_data[qid]['input_seq']
    ques, cand_entities, cand_classes, cand_paths, cand_rels = process_retriever_op(retrieved_data)
    return get_retriever_correctness(cand_entities, cand_classes, cand_paths, cand_rels, pred_lf)

# os.environ['http_proxy'] = HTTP_PROXY
# os.environ['https_proxy'] = HTTPS_PROXY
# # sentence_transformer_model = SentenceTransformer('mixedbread-ai/mxbai-embed-large-v1')
# sentence_transformer_model = None
# del os.environ['http_proxy']
# del os.environ['https_proxy']

def select_best_lf(pred_lf_choices: List[dict], orig_nl_qn: str, nl_semantic_feedback_mode: str, unanswerability: bool) -> Tuple[str, List[str]]:
    '''
    from a list of possible choices, we select the most likely correct choice using an 'nl_semantic_feedback_mode' based strategy. 
    pred_lf_choices = [
        {
            'pred_lf': ,
            'pred_nl': ,
            'pred_ans': ,
            'nl_semantic_check': ,
        }        
    ]
    Answerable setting- 
    1. select most common non empty answer & get all corresponding logical forms    [F1 maximization]
    2. of the corresponding pred_nls, use gpt filtering to select the best          [EM maximization]

    Unanswerable setting-
    1. if any one of the non empty answers occurs with frequency >=3,               super self-consistency
        - return that answer                                                        [F1 maximization]
        - of the corresponding pred_nls, use gpt filtering to select the best       [EM maximization]
    2. consider those logical forms for which `nl_semantic_check` = True
    (All these must be having empty answer)
        - if no logical form has nl_semantic_check= True, return (NK, [])               [F1&EM maximization]
        - if one or more logical form has nl_semantic_check= True, use gpt filtering    [EM maximization]   
    '''
    logger.info('----selecting best lf----')
    logger.info(pred_lf_choices)
    if pred_lf_choices == []:
        return 'NK', []
    
    if nl_semantic_feedback_mode == 'gpt_feedback':
        if not unanswerability: #answerability is guaranteed
            # remove empty answer lfs
            pred_lf_choices = [x for x in pred_lf_choices if (x['pred_ans']!= [])]
            if pred_lf_choices == []:
                return 'NK', []
            ## self-consistency strategy
            if len(pred_lf_choices) == 1:
                logger.info('only one choice, returning it')
                return pred_lf_choices[0]['pred_lf'], pred_lf_choices[0]['pred_ans']
            else:
                # Create a frequency dictionary for pred_ans values
                freq_dict = Counter(tuple(x['pred_ans']) for x in pred_lf_choices)
                # Find the pred_ans with maximum frequency
                max_freq_ans = max(freq_dict, key=freq_dict.get)
                # Select the corresponding pred_lf and pred_ans pair
                remaining_choices = [x for x in pred_lf_choices if tuple(x['pred_ans']) == max_freq_ans]
                return get_gpt_filtering_best_choice(remaining_choices, orig_nl_qn)
        else:
            # Create a frequency dictionary for pred_ans values
            freq_dict = Counter(tuple(x['pred_ans']) for x in pred_lf_choices)
            # Find the pred_ans with maximum frequency
            max_freq_ans = max(freq_dict, key=freq_dict.get)
            # Select the corresponding pred_lf and pred_ans pair
            remaining_choices = [x for x in pred_lf_choices if tuple(x['pred_ans']) == max_freq_ans]
            max_freq = len(remaining_choices)
            if (max_freq>=2) and (max_freq_ans != []): #super self consistency
                return get_gpt_filtering_best_choice(remaining_choices, orig_nl_qn)
            else:
                # step-1: select those logical forms for which `nl_semantic_check` = True
                nl_semantic_check_choices = [x for x in pred_lf_choices if x['nl_semantic_check']]
                if nl_semantic_check_choices == []:
                    return 'NK', []
                return get_gpt_filtering_best_choice(nl_semantic_check_choices, orig_nl_qn)
        
        # self-consistency strategy
        if len(pred_lf_choices) == 1:
            logger.info('only one choice, returning it')
            return pred_lf_choices[0]['pred_lf'], pred_lf_choices[0]['pred_ans']
        else:
            # Create a frequency dictionary for pred_ans values
            freq_dict = Counter(tuple(x['pred_ans']) for x in pred_lf_choices)
            # Find the pred_ans with maximum frequency
            max_freq_ans = max(freq_dict, key=freq_dict.get)
            # Select the corresponding pred_lf and pred_ans pair
            for choice in pred_lf_choices:
                if tuple(choice['pred_ans']) == max_freq_ans:
                    return choice['pred_lf'], choice['pred_ans']
        
    
    
    
    
    
    
    
    
    if nl_semantic_feedback_mode == 'always':
        ## self-consistency strategy
        # if len(pred_lf_choices) == 1:
        #     logger.info('only one choice, returning it')
        #     return pred_lf_choices[0]['pred_lf'], pred_lf_choices[0]['pred_ans']
        # else:
        #     # Create a frequency dictionary for pred_ans values
        #     freq_dict = Counter(tuple(x['pred_ans']) for x in pred_lf_choices)
        #     # Find the pred_ans with maximum frequency
        #     max_freq_ans = max(freq_dict, key=freq_dict.get)
        #     # Select the corresponding pred_lf and pred_ans pair
        #     for choice in pred_lf_choices:
        #         if tuple(choice['pred_ans']) == max_freq_ans:
        #             return choice['pred_lf'], choice['pred_ans']
        


        # ## baseline heuristic type strategy
        # if len(pred_lf_choices) == 1:
        #     logger.info('only one choice, returning it')
        #     return pred_lf_choices[0]['pred_lf'], pred_lf_choices[0]['pred_ans']
        # # atleast 2 choices -- 
        # if set(pred_lf_choices[0]['pred_ans']) == set(pred_lf_choices[1]['pred_ans']):
        #     logger.info('model seems confident about first answer, returning it')
        #     return pred_lf_choices[0]['pred_lf'], pred_lf_choices[0]['pred_ans']
        # if len(pred_lf_choices) > 2:
        #     logger.info('considering a third opinion')
        #     if set(pred_lf_choices[0]['pred_ans']) == set(pred_lf_choices[2]['pred_ans']):
        #         logger.info('model seems confident about first answer, returning it')
        #         return pred_lf_choices[0]['pred_lf'], pred_lf_choices[0]['pred_ans']
        #     if set(pred_lf_choices[1]['pred_ans']) == set(pred_lf_choices[2]['pred_ans']):
        #         logger.info('model seems confident about second answer, returning it')
        #         return pred_lf_choices[1]['pred_lf'], pred_lf_choices[1]['pred_ans']
        # logger.info('lack of consistency, returning finalmost prediction')
        # #TODO: what abt oscilations b/w n states? are all n same for us?
        # return pred_lf_choices[-1]['pred_lf'], pred_lf_choices[-1]['pred_ans']




        
        ## use a sentence transformer model to get the semantic similarity scores b/w the original question and pred_lf_choices[i]['pred_nl']
        # model = SentenceTransformer('bert-base-nli-mean-tokens')
        # model = SentenceTransformer('mixedbread-ai/mxbai-embed-large-v1')
        
        orig_embedding = sentence_transformer_model.encode([orig_nl_qn])
        # for sfr -- 
        # orig_embedding = sentence_transformer_model.encode([f'Instruct: Given a question, retrieve the semantically closest question \nQuery: {orig_nl_qn}'])
        best_score = -1
        best_lf = ''
        best_ans = []
        for choice in pred_lf_choices:
            pred_embedding = sentence_transformer_model.encode([choice['pred_nl']])
            similarity_score = cosine_similarity(orig_embedding, pred_embedding)[0][0]
            if similarity_score > best_score:
                best_score = similarity_score
                best_lf = choice['pred_lf']
                best_ans = choice['pred_ans']
        
        return best_lf, best_ans


        # using gpt-4

def select_best_lf_sc(pred_lf_choices: List[dict]) -> Tuple[str, List[str]]:
    logger.info('----selecting best lf using self consistency----')
    logger.info(pred_lf_choices)
    if pred_lf_choices == []:
        return 'NK', []
    
    # self-consistency strategy
    if len(pred_lf_choices) == 1:
        logger.info('only one choice, returning it')
        return pred_lf_choices[0]['pred_lf'], pred_lf_choices[0]['pred_ans']
    else:
        # Create a frequency dictionary for pred_ans values
        freq_dict = Counter(tuple(x['pred_ans']) for x in pred_lf_choices)
        # Find the pred_ans with maximum frequency
        max_freq_ans = max(freq_dict, key=freq_dict.get)
        # Select the corresponding pred_lf and pred_ans pair
        for choice in pred_lf_choices:
            if tuple(choice['pred_ans']) == max_freq_ans:
                return choice['pred_lf'], choice['pred_ans']

#         choices = '\n'.join([f"{idx+1}. pred_nl: {x['pred_nl'].replace(' distinct ', ' ')}" for idx, x in enumerate(pred_lf_choices)])
#         usr_prompt = f"""
# orig_nl_qn = {orig_nl_qn}

# {choices}

# of the {len(pred_lf_choices)} predicted nl questions, which is closest to the original nl question. Even if none is very close, return the one that is semantically closest? pls explain your answer as well"""
#         ans = ask_gpt_anything([{"role": "user", "content": usr_prompt}])
#         best_lf, best_ans = ([(x['pred_lf'], x['pred_ans']) for idx, x in enumerate(pred_lf_choices) if (x['pred_nl'].replace(' distinct ', ' ') in ans or f' {idx+1}. ' in ans)]+ [(pred_lf_choices[0]['pred_lf'], pred_lf_choices[0]['pred_ans'])])[0]
#         best_lf_results = [(x['pred_lf'], x['pred_ans']) for idx, x in enumerate(pred_lf_choices) if (x['pred_nl'].replace(' distinct ', ' ')  in ans or f' {idx+1}. ' in ans)]
#         logger.info(f'parsing results for best_lf: {best_lf_results}')
#         return best_lf, best_ans
    
def get_gpt_filtering_best_choice(pred_lf_choices: List[dict], orig_nl_qn: str)-> Tuple[str, List[str]]:
    '''
    out of k provided nl questions, identify the closest using gpt call 
    '''
    if len(pred_lf_choices) == 1:
        return pred_lf_choices[0]['pred_lf'], pred_lf_choices[0]['pred_ans']
    choices = '\n'.join([f"{idx+1}. pred_nl: {x['pred_nl'].replace(' distinct ', ' ')}" for idx, x in enumerate(pred_lf_choices)])
    usr_prompt = f"""
orig_nl_qn = {orig_nl_qn}

{choices}

of the {len(pred_lf_choices)} predicted nl questions, which is closest to the original nl question. Even if none is very close, return the one that is semantically closest? pls explain your answer as well"""
    ans = ask_gpt_anything([{"role": "user", "content": usr_prompt}])
    best_lf, best_ans = ([(x['pred_lf'], x['pred_ans']) for idx, x in enumerate(pred_lf_choices) if (x['pred_nl'].replace(' distinct ', ' ') in ans or f' {idx+1}. ' in ans)]+ [(pred_lf_choices[0]['pred_lf'], pred_lf_choices[0]['pred_ans'])])[0]
    best_lf_results = [(x['pred_lf'], x['pred_ans']) for idx, x in enumerate(pred_lf_choices) if (x['pred_nl'].replace(' distinct ', ' ')  in ans or f' {idx+1}. ' in ans)]
    logger.info(f'parsing results for best_lf: {best_lf_results}')
    if best_lf_results == []:
        # parsing fails, returning first option
        return [(x['pred_lf'], x['pred_ans']) for idx, x in enumerate(pred_lf_choices)][0]
    return best_lf, best_ans

def get_gpt_feedback(pred_nl_qn: str, orig_nl_qn: str, ini_prompt: str, retriever_op: str):
    '''
    verifier that tells whether the pred_lf matches the orig_nl_qn
    '''
    pred_nl_qn = pred_nl_qn.replace('distinct', '')
    ques, cand_entities, cand_classes, cand_paths, cand_rels = process_retriever_op(retriever_op)
    # nl-question |query| paths |entity| entities |class| classes |relation| relations
    retriever_op = f'|query| {"|".join(cand_paths.split("|")[:5])} |entity| {cand_entities} |class| {"|".join(cand_classes.split("|")[:10])} |relation| {"|".join(cand_rels.split("|")[:10])}'
    # prompt = f"Compare whether these 2 questions are semantically equivalent or not. If the only difference between the 2 questions is that one asks for a singular answer and the other asks for a plural answer, they are considered to be same.\n{ini_prompt}\npred question: {pred_nl_qn}\norig question: {orig_nl_qn}\nKB context: {retriever_op}\nexplanation: "
    ## experimenting w/o nl_semantic_prompt
    # prompt = f"Compare whether these 2 questions are semantically equivalent or not. If the only difference between the 2 questions is that one asks for a singular answer and the other asks for a plural answer, they are considered to be same.\n{ini_prompt}\npred question: {pred_nl_qn}\norig question: {orig_nl_qn}\nexplanation: "
    # prompt = f"Check whether the question we answer and the question originally asked are semantically equivalent or not.\n{ini_prompt}\nQuestion we answer: {pred_nl_qn}\nQuestion originally asked: {orig_nl_qn}\nexplanation: "
#     prompt = f"""Check whether the question we answer and the question originally asked are semantically equivalent or not. The question we answer is semantically equivalent to the question originally asked only if- 
# 1. the type of the answer returned by the question we answer is either same or more specific than the type asked for in the original question.
# 2. the reasoning steps followed by the question we answer are same as the reasoning steps followed by the question originally asked. 
# 3. the mathematical operators and logical operators used in the question we answer are same as the operators used in the question originaly asked. 
# {ini_prompt}
# Question we answer: {pred_nl_qn}
# Question originally asked: {orig_nl_qn}
# explanation: """

    prompt = f"""
{ini_prompt}
Question we answer: {pred_nl_qn}
Question originally asked: {orig_nl_qn}
explanation: """
    answer = ask_gpt_anything([{"role": "user", "content": prompt}])
    if ('Hence, they are same' in answer) or ('Hence, they are the same' in answer):
        logging.info('returning true')
        return True
    elif ('Hence, they are different' in answer):
        logging.info('returning false')
        return False
    elif ('they are same' in answer):
        logging.info('returning true')
        return True
    elif ('they are different' in answer):
        logging.info('returning false')
        return False
    elif 'same' in answer:
        logging.info('returning true')
        return True
    else:
        logging.info('returning false')
        return False


def feedback_prompting():
    pred_lf_file = 'temp/webqsp_src_grailqa_tgt_parsed_data.json'
    # pred_lf_file = 'temp/grailqa_src_webqsp_tgt_parsed_data.json' #TODO: change this to the correct path
    pred_lf_choices_dataset = load_json(pred_lf_file)
    dataset = load_json('../data/webqsp_grailqa_dev200/webqsp_grail_dev_200_riya.json') #TODO: change this to the correct path
    # dataset = load_json('../data/grailWebqspRiyaDev200/test/webqsp_0107.dev200.json')
    # read the prompt.txt file
    ini_prompt = open('../data/webqsp_grailqa_dev200/nl_semantic_prompt.txt').read()
    # ini_prompt = open('../data/grailWebqspRiyaDev200/train/nl_semantic_prompt.txt').read()
    # now iterate through the pred_lf_choices and ask_gpt_anything(prompt+pred_lf_choices[i]['pred_nl'])
    for  idx, choices_for_item in enumerate(pred_lf_choices_dataset):
        print('qid: ', dataset[idx]['qid'])
        model_confidence = 0
        for choice_idx, choice in enumerate(choices_for_item['pred_lf_choices']):
            print(choice)
            pred_nl = choice['pred_nl']
            pred_lf = choice['pred_lf']
            if 'LIMIT 1' in pred_lf and not('MAX' in pred_lf or 'MIN' in pred_lf or 'GROUP BY' in pred_lf or 'ORDER BY' in pred_lf):
                print(pred_lf)
                print('the logical form has an unnecessary singular constraint, skipping...')
                continue
            prompt = f"{ini_prompt}\npred question: {pred_nl}\norig question: {dataset[idx]['question']}\nexplanation: "
            print('--asking--')
            print(prompt)
            answer = ask_gpt_anything([{"role": "user", "content": prompt}])
            print(answer)
            if 'Hence, they are same' in answer:
                dataset[idx]['pred_lf'] = choice['pred_lf']
                dataset[idx]['pred_ans'] = choice['pred_ans']
                print(f'success at #{choice_idx} round')
                model_confidence = 1
                break
        if 'pred_lf' not in dataset[idx]:
            print('search does not terminate...')
            # dataset[idx]['pred_lf'] = choices_for_item['pred_lf_choices'][-1]['pred_lf']
            # dataset[idx]['pred_ans'] = choices_for_item['pred_lf_choices'][-1]['pred_ans']
            # self-consistency strategy
            if len(choices_for_item['pred_lf_choices']) == 1:
                print('only one choice, returning it')
                dataset[idx]['pred_lf'] = choices_for_item['pred_lf_choices'][0]['pred_lf']
                dataset[idx]['pred_ans'] = choices_for_item['pred_lf_choices'][0]['pred_ans']
            else:
                # Create a frequency dictionary for pred_ans values
                freq_dict = Counter(tuple(x['pred_ans']) for x in choices_for_item['pred_lf_choices'])
                # Find the pred_ans with maximum frequency
                max_freq_ans = max(freq_dict, key=freq_dict.get)
                # Select the corresponding pred_lf and pred_ans pair
                for choice in choices_for_item['pred_lf_choices']:
                    if tuple(choice['pred_ans']) == max_freq_ans:
                        dataset[idx]['pred_lf'] = choice['pred_lf']
                        dataset[idx]['pred_ans'] = choice['pred_ans']
        print('---final report---')
        print('model confidence: ', model_confidence)
        gt_ans = [ans['answer_argument'] for ans  in dataset[idx]['answer']]
        print('correct answer: ', set(dataset[idx]['pred_ans']) == set(gt_ans))
        dump_json(dataset, 'temp/last_step_feedback_webqsp_src_grailqa_tgt_v2.json')



reverse_properties_f = {}
reverse_properties_b = {}
reverse_properties_file = "../data/freebase/reverse_properties.txt"

with open(reverse_properties_file, 'r') as f:
    for line in f:
        reverse_properties_f[line.split('\t')[0]] = line.split('\t')[1].replace('\n', '')
        reverse_properties_b[line.split('\t')[1].replace('\n', '')] = line.split('\t')[0].replace('\n', '')


def em_score(pred_lf, gt_item, reverse_properties_f, reverse_properties_b):
    pred_lf = pred_lf.replace('ns:', ':')
    if gt_item['s_expression'] == 'NK' and pred_lf == 'NK':
        return 1
    if (gt_item['s_expression'] == 'NK') or (pred_lf == 'NK'):
        return 0
    rel_list = []
    for data_edge_idx in range(len(gt_item['graph_query']['edges'])):
        rel = gt_item['graph_query']['edges'][data_edge_idx]['relation']
        rel_list.append(rel)
        
    ##FOR CLASS/ENTITY
    cls_list = []
    entity_list = []
    for data_node_idx in range(len(gt_item['graph_query']['nodes'])):
        node_type = gt_item['graph_query']['nodes'][data_node_idx]['node_type']
        if node_type == "class": # for all nodes
        #if node_type == "class" and gt_item['graph_query']['nodes'][data_node_idx]['nid']==0: # for answer nodes
            cls_list.append(gt_item['graph_query']['nodes'][data_node_idx]['id'])
        if node_type == "entity":
            entity_list.append(gt_item['graph_query']['nodes'][data_node_idx]['id'])
    #print(entity_list)
    for e in entity_list:
        if e in pred_lf:
            continue
        else:
            print('entity missing')
            print(gt_item)
            return 0
    
    for rel in rel_list:
        if rel in reverse_properties_f.keys():
            try:
                rel_r=reverse_properties_f[rel]
            except:
                rel_r=rel
        else:
            try:
                rel_r=reverse_properties_b[rel]
            except:
                rel_r=rel
        if rel in pred_lf or rel_r in pred_lf :
            #pred_lf=pred_lf.replace(rel,"")
            #pred_lf=pred_lf.replace(rel_r,"")
            continue
        else:
            #print(gt_item,pred_lf)
            #sys.exit(0)
            print('rel missing')
            print(gt_item)
            return 0
    
    # for c in cls_list:
    #         if ":type.object.type :"+c in gt_item["sparql_query"]:
    #         #if True:
    #             if ":type.object.type :"+c in pred_lf:
    #                 continue
    #             else:
    #                 print(gt_item["sparql_query"])
    #                 print(pred_lf)
    #                 print(c)
    #                 print("==================================")
    #                 #print(pred_lf)
    #                 #sys.exit(0)
    #                 return 0
    

    return 1



def get_acc_f1(preds_data: List[dict]):
    def get_data_from_qid(qid: str, data: List[dict]) -> dict:
        for d in data:
            if d['qid'] == qid:
                return d
        return {'gt_ans': []}
    f1_scores = []
    em_scores = []
    l_f1_scores = []
    wrongs = [] # defined as f1<1 for now
    for pred_data in preds_data:
        gt_ans = [str(x['answer_argument']) for x in pred_data['answer']]
        if 'pred_ans' in pred_data.keys():
            pred_ans = pred_data['pred_ans']
        else:
            pred_ans = []
            pred_data['pred_lf'] = "NK"
        all_possible_answers = list(set(gt_ans + pred_ans))
        
        # Convert to binary labels
        gt_ans_set = set(gt_ans)
        pred_ans_set = set(pred_ans)
        gt_labels = [1 if ans in gt_ans_set else 0 for ans in all_possible_answers]
        pred_labels = [1 if ans in pred_ans_set else 0 for ans in all_possible_answers]
        # Calculate F1 score
        if gt_labels != []:
            f1 = f1_score(gt_labels, pred_labels, average='binary')
        else:
            if pred_labels == gt_labels:
                f1 = 1
            else:
                f1 = 0
        if 'Organswer' in pred_data: 
            l_gt_ans = [str(x['answer_argument']) for x in pred_data['Organswer']]
            l_all_possible_answers = list(set(l_gt_ans + pred_ans))
            l_gt_ans_set = set(l_gt_ans)
            l_gt_labels = [1 if ans in l_gt_ans_set else 0 for ans in l_all_possible_answers]
            l_pred_labels = [1 if ans in pred_ans_set else 0 for ans in l_all_possible_answers]
            l_pr = max(precision_score(l_gt_labels, l_pred_labels, average='binary'), precision_score(gt_labels, pred_labels, average='binary'))        
            l_re = max(recall_score(l_gt_labels, l_pred_labels, average='binary'), recall_score(gt_labels, pred_labels, average='binary'))
            if (l_gt_labels == l_pred_labels) or (gt_labels == pred_labels):
                l_pr = 1
                l_re = 1
            if l_pred_labels == [0]*len(l_pred_labels) or pred_labels == [0]*len(pred_labels):
                l_pr = 1
            if l_gt_labels == [0]*len(l_gt_labels) or gt_labels == [0]*len(gt_labels):
                l_re = 1
            if(l_pr +l_re == 0):
                l_f1 = 0
            else:
                l_f1 = (2*l_pr*l_re)/(l_pr+l_re)
            
            l_f1_scores.append(l_f1)

        em = em_score(pred_data['pred_lf'], pred_data, reverse_properties_f, reverse_properties_b)
        f1_scores.append(f1)
        em_scores.append(em)
        if l_f1<1:
            wrongs.append(pred_data['qid'])
        # print(f1)
        # print('avg: ', sum(f1_scores) / len(f1_scores) if f1_scores else 0)
    # print(wrongs)

    # Calculate average F1 score
    f1_avg = sum(f1_scores) / len(f1_scores) if f1_scores else 0
    em_avg = sum(em_scores) / len(em_scores) if em_scores else 0
    l_f1_avg = sum(l_f1_scores) / len(l_f1_scores) if l_f1_scores else 0
    return f1_avg, em_avg, l_f1_avg

def get_em_f1(pred_path):
    with open(pred_path) as f:
        data = json.load(f)
        print(get_acc_f1(data))

# print("Calculating EM F1")
# get_em_f1("/home/scai/phd/aiz248314/KBQA/FuSIC-KBQA-EGF/fusic-kbqa-egf/result/questions_v1.json____graphqa_test_50A_50U.json_2025-02-01_05:20:33.657478.json")
if __name__ == '__main__':
    get_em_f1("/home/scai/phd/aiz248314/KBQA/FuSIC-KBQA-EGF/fusic-kbqa-egf/outputs/graphqa250+250/result.json")
    # get_em_f1("/home/scai/phd/aiz248314/KBQA/FuSIC-KBQA-EGF/data/unanswerable_webqsp_src_graphqa_tgt/main_250A_only.json")
    # get_em_f1("/home/scai/phd/aiz248314/KBQA/FuSIC-KBQA-EGF/fusic-kbqa-egf/result/questions_v1.json____graphqa_test_50A_50U.json_2025-02-01_05:20:33.657478.json")
    # feedback_prompting()
    # import ipdb; ipdb.set_trace()

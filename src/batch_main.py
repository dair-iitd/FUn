import os
import sys
from collections import defaultdict
from logic_form_util import lisp_to_sparql
import random
from typing import Any, Union, List
import my_secrets
from tqdm import tqdm
from select_exemplars import select_exemplars
from utils import load_json, dump_json, get_answer, ask_gpt_anything, is_type_node, get_subset, check_type, get_grounded, select_best_lf, naturalize_query, get_gpt_feedback, get_topic_entity_mids, mid_to_friendly, correct_syntax
from prompts import construct_prompt, construct_egf_prompt, construct_intermediate_prompt, construct_lf_semantic_feedback_prompt, construct_nl_semantic_feedback_prompt, construct_grounding_prompt, construct_float_suffix_prompt, construct_qans_prompt, construct_mult_prompt
random.seed(100)
import json
import logging
import datetime, time
import openai

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
    # return task

def load_json_dict(path):
    test_data = {}
    with open(path) as f:
        data = json.load(f)
        for t in data:
            test_data[t['qid']] = t
    
    return test_data

def get_batch_job(client, id):
    batch_job = client.batches.retrieve(id)
    print(batch_job)
    return batch_job

def get_result(client, batch_job, result_file_name):
    result_file_id = batch_job.output_file_id
    result = client.files.content(result_file_id).content
    with open(f'./batch_runs/results/{batch_job.id}.jsonl', 'wb') as file:
        file.write(result)
    
    results = {}
    with open(f'./batch_runs/results/{batch_job.id}.jsonl', 'r') as file:
        for line in file:
            # Parsing the JSON string into a dict and appending to the list of results
            json_object = json.loads(line.strip())
            results[int(json_object['custom_id'])] = json_object['response']['body']['choices'][0]['message']['content']
    return results


def gen_initial_batch(train_data: List[dict], test_data: List[dict], retriever_augmented_train : str, retriever_augmented_test : str, func_predictions_test : Union[str, None], num_retries : int, exemplar_selection : str, num_shots : int, output_dir : str, program_lang : str, naturalize_varnames: bool = False, syntax_feedback: bool= False, lf_semantic_feedback: bool = False, cvt_feedback: bool = False, nl_semantic_feedback: bool = False, nl_semantic_feedback_mode: str = 'None', nl_semantic_feedback_prompt: str = 'None', unanswerability: bool = False)-> None: 
    retriever_augmented_test_data = load_json(retriever_augmented_test)
    flags= {}
    cur_time= str(datetime.datetime.now()).replace(' ', '_')
    task_name = f'{os.path.basename(input_train_file)}____{os.path.basename(input_test_file)}_{cur_time}'  
    batch_tasks = []
    for idx, question in tqdm(enumerate(test_data) ,total = len(test_data)): 
        log_dict = {}
        prompt = construct_prompt([], str(question['qid']), train_data, [], retriever_augmented_test_data, program_lang, naturalize_varnames, unanswerability)

        batch_tasks.append(create_batch_(str(question['qid']), prompt))

    with open(f'./batch_runs/batches/{task_name}.jsonl', 'w') as file:
        file.write('\n'.join(batch_tasks))

    client = openai.OpenAI(api_key=my_secrets.key)
    batch_file = client.files.create(
                                        file=open(f'./batch_runs/batches/{task_name}.jsonl', "rb"),
                                        purpose="batch"
                                        )      
    print(batch_file) 

    batch_job = client.batches.create(
                                        input_file_id=batch_file.id,
                                        endpoint="/v1/chat/completions",
                                        completion_window="24h"
                                        ) 

    with open(f'./batch_runs/JOBs.log', 'a+') as file:
        file.write(f"{task_name}\t:\t{batch_job.id}\n")
 

def gen_query_batch(train_data: List[dict], test_data: List[dict], retriever_augmented_train : str, retriever_augmented_test : str, func_predictions_test : Union[str, None], num_retries : int, exemplar_selection : str, num_shots : int, output_dir : str, program_lang : str, naturalize_varnames: bool = False, syntax_feedback: bool= False, lf_semantic_feedback: bool = False, cvt_feedback: bool = False, nl_semantic_feedback: bool = False, nl_semantic_feedback_mode: str = 'None', nl_semantic_feedback_prompt: str = 'None', unanswerability: bool = False, logger = logging.getLogger(__name__))-> None: 
    stt_num_retries = num_retries
    f = open('./prompt.txt','w')
    retriever_augmented_train_data = load_json(retriever_augmented_train)
    retriever_augmented_test_data = load_json(retriever_augmented_test)
    fname=  f"{os.path.basename(input_train_file)}____{os.path.basename(input_test_file)}_{str(datetime.datetime.now()).replace(' ', '_')}"
    prediction_dump_file=f"{fname}.json"
    retriever_augmented_test_data_dict= load_json_dict(retriever_augmented_test)
    id = "batch_67ab4c667e008190a164b602c8ff8e0e"
    client = openai.OpenAI(api_key=my_secrets.key)
    batch_job = get_batch_job(client, id)
    result= get_result(client, batch_job, fname)
    logs = []
    flags= {}
    for idx, question in tqdm(enumerate(test_data) ,total = len(test_data)): 
        log_dict = {}
        num_retries = stt_num_retries
        logger.info(f'---------------------------------------------------------------------------------------------------------------------------------')
        logger.info(f'{idx}: {question}')
        # time.sleep(60)
        log_dict['qid'] = str(question['qid'])
        topic_entity_nodes = get_topic_entity_mids(retriever_augmented_test_data[str(question['qid'])]['input_seq'])
        logging.info(f'topic entity nodes: {topic_entity_nodes}')
        log_dict['prompt'] = prompt
        latest_prompt = 'vanilla'
        print(log_dict['qid'], file = f)
        print(prompt, file=f)
        pred_lf = result[question['qid']]
        # time.sleep(60)

        # gt_lf = question['sparql_query']
        if '{' not in pred_lf:
            # probably there is some error msg by gpt..
            pred_lf = 'NK'
        if 'LIMIT 1' in pred_lf and not('MAX' in pred_lf or 'MIN' in pred_lf or 'GROUP BY' in pred_lf or 'ORDER BY' in pred_lf):
            logger.info('singular plural issue detected! removing unnecessary constraint...')
            logger.info(pred_lf)
            pred_lf = pred_lf.replace('LIMIT 1', '')
        log_dict['pred_lf'] = pred_lf
        pred_ans = get_answer(pred_lf, syntax_feedback)
        if pred_ans != []:
            if pred_ans[0] == 'syntax_error':
                if syntax_feedback:
                    pred_lf = correct_syntax(pred_lf, pred_ans[1])
                    pred_ans = get_answer(pred_lf, syntax_feedback)
                    if pred_ans != []:
                        if pred_ans[0] == 'syntax_error':
                            pred_ans = []
        log_dict['pred_ans'] = pred_ans
        if pred_ans == ['nonsense']:
            test_data[idx]['pred_lf'] = pred_lf
            test_data[idx]['pred_ans'] = pred_ans
            dump_json(test_data, os.path.join(output_dir, 'predictions.json'))
            logs.append(log_dict)
            dump_json(logs, os.path.join(output_dir, 'logs.json'))
            continue
        grounded_feedback = get_grounded(pred_lf, str(question['qid']), retriever_augmented_test_data)
        if grounded_feedback != 'correct':
            is_grounding_issue = True
        else:
            is_grounding_issue = False
        log_dict['is_grounding_issue'] = is_grounding_issue
        if len(pred_ans) == 1 and pred_ans[0] in topic_entity_nodes:
            logger.info('answer same as topic entity node! provide feedback...')
            is_qans_issue = True
        else:
            is_qans_issue = False
        if (len(pred_ans) == 1) and (pred_ans[0] == 'multiple_vars'):
            logger.info('returning multiple variables instead of single! provide feedback...')
            is_mult_issue = True
        else:
            is_mult_issue = False
        if (('>=' in pred_lf or '<=' in pred_lf or ' > ' in pred_lf or ' < ' in pred_lf) and '<http://www.w3.org/2001/XMLSchema#float>' not in pred_lf and '^^xsd:dateTime' not in pred_lf):
            is_float_suffix_issue = True 
        else:
            is_float_suffix_issue = False
        if 'LIMIT 1' in pred_lf and not('MAX' in pred_lf or 'MIN' in pred_lf or 'GROUP BY' in pred_lf or 'ORDER BY' in pred_lf):
            logger.info('singular plural issue detected! removing unnecessary constraint...')
            logger.info(pred_lf)
            pred_lf = pred_lf.replace('LIMIT 1', '')
        log_dict['is_float_issue'] = is_float_suffix_issue
        best_ans = pred_ans
        best_lf = pred_lf
        is_nl_semantic_issue = False
        if nl_semantic_feedback and nl_semantic_feedback_mode == 'gt':
            # if we're providing a gt semantic discriminator, we must have gt answers at our disposal  
            # "answer": [{"answer_type": "Entity", "answer_argument": "m.0b787yg", "entity_name": "Set Designer"}]
            gt_ans = [ans['answer_argument'] for ans  in question['answer']]
            if (set(gt_ans) != set(pred_ans)) and ((len(pred_ans) > 0) or unanswerability): #TODO: for now we assume that semantically correct lf is equivalent to non-empty answer
                is_nl_semantic_issue = True
        if nl_semantic_feedback and nl_semantic_feedback_mode == 'always':
            gt_ans = [ans['answer_argument'] for ans  in question['answer']]
            is_nl_semantic_issue = (len(pred_ans) > 0) or unanswerability
        if nl_semantic_feedback and nl_semantic_feedback_mode == 'gpt_feedback':
            query_we_answer = naturalize_query(pred_lf)
            is_nl_semantic_issue = not (get_gpt_feedback(query_we_answer, question['question'], nl_semantic_feedback_prompt, '|query|'+retriever_augmented_test_data[str(question['qid'])]['input_seq'].split('|query|')[-1])) #TODO: check this!!
        if not nl_semantic_feedback:
            query_we_answer = pred_lf
        gt_ans = [ans['answer_argument'] for ans  in question['answer']]
        log_dict['is_nl_semantic_issue'] = is_nl_semantic_issue
        is_intermediate_node = is_type_node(pred_ans) and cvt_feedback 
        log_dict['is_intermediate_node'] = is_intermediate_node
        if lf_semantic_feedback and (pred_ans == [] or pred_ans == ['0']):
            semantic_feedback = check_type(pred_lf)
            if semantic_feedback != 'correct':
                is_semantic_issue = True
            else:
                is_semantic_issue = False
        else:
            is_semantic_issue = False
        log_dict['is_lf_semantic_issue'] = is_semantic_issue
        pred_lf_choices: List[dict] = [] # for algos that rely on multiple lf choices
        is_validator_happy = True
        all_feedbacks = []
        if ((len(pred_ans) == 0 ) or is_intermediate_node or is_semantic_issue or is_nl_semantic_issue or is_grounding_issue or is_float_suffix_issue or is_qans_issue or is_mult_issue) and pred_lf != 'NK': #TODO: pls add `and not unanswerability` ASAP!!
            is_validator_happy = False
            while num_retries:
                if is_grounding_issue:# grounding issue is most major!
                    prompt = construct_grounding_prompt(prompt, pred_lf, program_lang,  grounded_feedback)
                    logging.info('grounding issue detected!!')
                    latest_prompt = 'grounding'
                    all_feedbacks.append(latest_prompt)
                elif is_qans_issue:
                    prompt = construct_qans_prompt(prompt, pred_lf, program_lang, mid_to_friendly(':'+pred_ans[0]))
                    logging.info('QAns issue detected!!')
                    latest_prompt = 'qans'
                    all_feedbacks.append(latest_prompt)
                elif is_mult_issue:
                    prompt = construct_mult_prompt(prompt, pred_lf, program_lang)
                    logging.info('Multiple answers issue detected!!')
                    # print('Multiple answers issue detected!!')
                    latest_prompt = 'mult'
                    all_feedbacks.append(latest_prompt)
                elif is_float_suffix_issue: # pls add the float suffix
                    prompt = construct_float_suffix_prompt(prompt, pred_lf, program_lang)
                    logging.info('float suffix issue detected!!')
                    latest_prompt = 'float_suffix'
                    all_feedbacks.append(latest_prompt)
                # if (len(pred_ans) > 0) and cvt_feedback and not(is_nl_semantic_issue): #only intermediate issue #TODO: literals returned are not cvts!!!
                elif is_intermediate_node:
                    prompt = construct_intermediate_prompt(prompt, pred_lf, program_lang)
                    latest_prompt = 'intermediate'
                    all_feedbacks.append(latest_prompt)
                elif is_semantic_issue: # logical form semantic issue
                    semantic_feedback = check_type(pred_lf)
                    prompt = construct_lf_semantic_feedback_prompt(prompt, pred_lf, program_lang, semantic_feedback)
                    latest_prompt = 'lf_semantic'
                    all_feedbacks.append(latest_prompt)
                elif is_nl_semantic_issue: # natural language semantic issue
                    logger.info('NL semantic issue detected !!')
                    #TODO: check this!!!
                    prompt, query_we_answer = construct_nl_semantic_feedback_prompt(prompt, pred_lf, program_lang, question['question'])
                    pred_lf_choices.append({'pred_lf': pred_lf, 'pred_nl': query_we_answer, 'pred_ans': pred_ans, 'nl_semantic_check': False})
                    latest_prompt = 'nl_semantic'
                    all_feedbacks.append(latest_prompt)
                elif pred_ans == []: 
                    prompt = construct_egf_prompt(prompt, pred_lf, program_lang)
                    pred_lf_choices.append({'pred_lf': pred_lf, 'pred_nl': query_we_answer, 'pred_ans': pred_ans, 'nl_semantic_check': True})
                    latest_prompt = 'egf'
                    all_feedbacks.append(latest_prompt)
                else:
                    logger.info('no new prompt...nothing further to try')
                    num_retries = 0
                pred_lf = ask_gpt_anything(prompt)
                if '{' not in pred_lf:
                    # probably an error message returned by gpt...
                    pred_lf = 'NK'
                if pred_lf == 'NK':
                    break
                if 'LIMIT 1' in pred_lf and not('MAX' in pred_lf or 'MIN' in pred_lf or 'GROUP BY' in pred_lf or 'ORDER BY' in pred_lf):
                    logger.info('singular plural issue detected! removing unnecessary constraint...')
                    logger.info(pred_lf)
                    pred_lf = pred_lf.replace('LIMIT 1', '')
                pred_ans = get_answer(pred_lf, syntax_feedback)
                if pred_ans != []:
                    if pred_ans[0] == 'syntax_error':
                        pred_lf = correct_syntax(pred_lf, pred_ans[1])
                        pred_ans = get_answer(pred_lf, syntax_feedback)
                        if pred_ans != []:
                            if pred_ans[0] == 'syntax_error': # we conuldn't correct the error despite efforts
                                pred_ans = []
                if pred_ans == ['nonsense']:
                    break
                if ((pred_ans == ['0']) and not unanswerability):
                    pred_ans = [] # getting answer '0' (for a count question) means that the answer is empty
                is_intermediate_node = is_type_node(pred_ans) and cvt_feedback
                is_semantic_issue = (len(pred_ans) == 0 or pred_ans == ['0']) and (check_type(pred_lf) != 'correct') and lf_semantic_feedback
                if nl_semantic_feedback_mode == 'gt':
                    is_nl_semantic_issue = ((len(pred_ans) > 0) or unanswerability) and (set(gt_ans) != set(pred_ans)) and nl_semantic_feedback#TODO: len(pred_ans) cond only for answerable
                elif nl_semantic_feedback_mode == 'always':
                    is_nl_semantic_issue = ((len(pred_ans) > 0) or unanswerability)  and nl_semantic_feedback
                elif nl_semantic_feedback_mode == 'gpt_feedback':
                    query_we_answer = naturalize_query(pred_lf)
                    is_nl_semantic_issue = ((len(pred_ans) > 0)or unanswerability)  and nl_semantic_feedback and not (get_gpt_feedback(query_we_answer, question['question'], nl_semantic_feedback_prompt,  '|query|'+retriever_augmented_test_data[str(question['qid'])]['input_seq'].split('|query|')[-1]))
                elif not nl_semantic_feedback:
                    query_we_answer = pred_lf
                grounded_feedback = get_grounded(pred_lf, str(question['qid']), retriever_augmented_test_data)
                if grounded_feedback != 'correct':
                    is_grounding_issue = True
                else:
                    is_grounding_issue = False
                if (len(pred_ans) == 1):
                    if pred_ans[0] in topic_entity_nodes: 
                        is_qans_issue = True
                    else:
                        is_qans_issue = False
                else:
                    is_qans_issue = False
                if (len(pred_ans) == 1):
                    if pred_ans[0] == 'multiple_vars': 
                        is_mult_issue = True
                    else:
                        is_mult_issue = False
                else:
                    is_mult_issue = False
                if (('>=' in pred_lf or '<=' in pred_lf or ' > ' in pred_lf or ' < ' in pred_lf) and ('<http://www.w3.org/2001/XMLSchema#float>' not in pred_lf) and ('^^xsd:dateTime' not in pred_lf)): #TODO: ensure it isn't datetime as well!!
                    is_float_suffix_issue = True 
                else:
                    is_float_suffix_issue = False
                
                logger.info(f'pred_ans: {pred_ans}')
                if (not is_semantic_issue):
                        best_ans = pred_ans
                        best_lf = pred_lf
                if ((len(pred_ans) > 0)) and (not(is_intermediate_node)) and (not(is_semantic_issue)) and (not(is_nl_semantic_issue) and (not(is_qans_issue)) and (not(is_mult_issue))):#TODO: pls add  `or unanswerability` ASAP!!!!
                    logger.info('egf at work!')
                    is_validator_happy = True
                    logger.info(f'pred_ans: {pred_ans}')
                    break
                num_retries -= 1
        else:
            is_validator_happy = True
        if nl_semantic_feedback_mode == 'always' or nl_semantic_feedback_mode == 'gpt_feedback':
            if (pred_lf == 'NK'):
                best_lf = 'NK'
                best_ans = []
            if (pred_ans != [] or unanswerability):
                prompt, query_we_answer = construct_nl_semantic_feedback_prompt(prompt, pred_lf, program_lang, question['question'])
                if not(is_semantic_issue) and not(is_mult_issue) and not(is_float_suffix_issue) and not(is_grounding_issue) and not(is_qans_issue) and not(is_intermediate_node):
                    pred_lf_choices.append({'pred_lf': pred_lf, 'pred_nl': query_we_answer, 'pred_ans': pred_ans, 'nl_semantic_check': not (is_nl_semantic_issue)})
            if (not is_validator_happy )and (pred_lf != 'NK'):
                best_lf, best_ans = select_best_lf(pred_lf_choices, question['question'], nl_semantic_feedback_mode, unanswerability) #TODO: check this!!
            if (not is_validator_happy) and unanswerability:
                # logger.info('validator aint happy and we live in unanswerable world')
                # best_lf = 'NK'
                # best_ans = []
                if best_lf == 'NK':
                    logger.info('validator aint happy and we live in unanswerable world -- schema level unanswerable')
                elif best_ans != []:
                    logger.info('super self consistency')
                else:
                    logger.info('data level unanswerable')
        logger.info(f'pred_ans: {pred_ans}')
        best_ans_final = [b for b in best_ans if b not in topic_entity_nodes]
        best_ans = best_ans_final
        logger.info(f'best_ans: {best_ans}') #TODO: maybe have a better algo for selecting the best answer
        logger.info(f'gt ans: {gt_ans}')
        logger.info(f'latest prompt: {latest_prompt}')
        logger.info(f'total retries: {stt_num_retries - num_retries}')
        if pred_lf == 'NK':
            is_validator_happy = True
        logger.info(f'---report: {question["qid"]}---\nans match: {set(gt_ans) == set(best_ans)}\nconfident:{is_validator_happy}\ngtype: {"K" if question["s_expression"]!= "NK" else "NK"}\nptype: {"K" if get_grounded(question["sparql_query"], str(question["qid"]), retriever_augmented_test_data)=="correct" else "NK"}\nall prompts: {all_feedbacks}')

        test_data[idx]['pred_lf'] = best_lf
        test_data[idx]['pred_ans'] = best_ans
        dump_json(test_data[:idx+1], os.path.join(output_dir, prediction_dump_file))



def gen_query(train_data: List[dict], test_data: List[dict], retriever_augmented_train : str, retriever_augmented_test : str, func_predictions_test : Union[str, None], num_retries : int, exemplar_selection : str, num_shots : int, output_dir : str, program_lang : str, naturalize_varnames: bool = False, syntax_feedback: bool= False, lf_semantic_feedback: bool = False, cvt_feedback: bool = False, nl_semantic_feedback: bool = False, nl_semantic_feedback_mode: str = 'None', nl_semantic_feedback_prompt: str = 'None', unanswerability: bool = False, logger = logging.getLogger(__name__))-> None: 
    stt_num_retries = num_retries
    f = open('./prompt.txt','w')
    retriever_augmented_train_data = load_json(retriever_augmented_train)
    retriever_augmented_test_data = load_json(retriever_augmented_test)
    prediction_dump_file=f"{os.path.basename(input_train_file)}____{os.path.basename(input_test_file)}_{str(datetime.datetime.now()).replace(' ', '_')}.json"

    logs = []
    flags= {}
    for idx, question in tqdm(enumerate(test_data) ,total = len(test_data)): 
        log_dict = {}
        num_retries = stt_num_retries
        logger.info(f'---------------------------------------------------------------------------------------------------------------------------------')
        logger.info(f'{idx}: {question}')
        # time.sleep(60)
        log_dict['qid'] = str(question['qid'])
        prompt = construct_prompt([], str(question['qid']), train_data, retriever_augmented_train_data, retriever_augmented_test_data, program_lang, naturalize_varnames, unanswerability)
        topic_entity_nodes = get_topic_entity_mids(retriever_augmented_test_data[str(question['qid'])]['input_seq'])
        logging.info(f'topic entity nodes: {topic_entity_nodes}')
        log_dict['prompt'] = prompt
        latest_prompt = 'vanilla'
        print(log_dict['qid'], file = f)
        print(prompt, file=f)
        pred_lf = ask_gpt_anything(prompt)
        # time.sleep(60)

        # gt_lf = question['sparql_query']
        if '{' not in pred_lf:
            # probably there is some error msg by gpt..
            pred_lf = 'NK'
        if 'LIMIT 1' in pred_lf and not('MAX' in pred_lf or 'MIN' in pred_lf or 'GROUP BY' in pred_lf or 'ORDER BY' in pred_lf):
            logger.info('singular plural issue detected! removing unnecessary constraint...')
            logger.info(pred_lf)
            pred_lf = pred_lf.replace('LIMIT 1', '')
        log_dict['pred_lf'] = pred_lf
        pred_ans = get_answer(pred_lf, syntax_feedback)
        if pred_ans != []:
            if pred_ans[0] == 'syntax_error':
                if syntax_feedback:
                    pred_lf = correct_syntax(pred_lf, pred_ans[1])
                    pred_ans = get_answer(pred_lf, syntax_feedback)
                    if pred_ans != []:
                        if pred_ans[0] == 'syntax_error':
                            pred_ans = []
        log_dict['pred_ans'] = pred_ans
        if pred_ans == ['nonsense']:
            test_data[idx]['pred_lf'] = pred_lf
            test_data[idx]['pred_ans'] = pred_ans
            dump_json(test_data, os.path.join(output_dir, 'predictions.json'))
            logs.append(log_dict)
            dump_json(logs, os.path.join(output_dir, 'logs.json'))
            continue
        grounded_feedback = get_grounded(pred_lf, str(question['qid']), retriever_augmented_test_data)
        if grounded_feedback != 'correct':
            is_grounding_issue = True
        else:
            is_grounding_issue = False
        log_dict['is_grounding_issue'] = is_grounding_issue
        if len(pred_ans) == 1 and pred_ans[0] in topic_entity_nodes:
            logger.info('answer same as topic entity node! provide feedback...')
            is_qans_issue = True
        else:
            is_qans_issue = False
        if (len(pred_ans) == 1) and (pred_ans[0] == 'multiple_vars'):
            logger.info('returning multiple variables instead of single! provide feedback...')
            is_mult_issue = True
        else:
            is_mult_issue = False
        if (('>=' in pred_lf or '<=' in pred_lf or ' > ' in pred_lf or ' < ' in pred_lf) and '<http://www.w3.org/2001/XMLSchema#float>' not in pred_lf and '^^xsd:dateTime' not in pred_lf):
            is_float_suffix_issue = True 
        else:
            is_float_suffix_issue = False
        if 'LIMIT 1' in pred_lf and not('MAX' in pred_lf or 'MIN' in pred_lf or 'GROUP BY' in pred_lf or 'ORDER BY' in pred_lf):
            logger.info('singular plural issue detected! removing unnecessary constraint...')
            logger.info(pred_lf)
            pred_lf = pred_lf.replace('LIMIT 1', '')
        log_dict['is_float_issue'] = is_float_suffix_issue
        best_ans = pred_ans
        best_lf = pred_lf
        is_nl_semantic_issue = False
        if nl_semantic_feedback and nl_semantic_feedback_mode == 'gt':
            # if we're providing a gt semantic discriminator, we must have gt answers at our disposal  
            # "answer": [{"answer_type": "Entity", "answer_argument": "m.0b787yg", "entity_name": "Set Designer"}]
            gt_ans = [ans['answer_argument'] for ans  in question['answer']]
            if (set(gt_ans) != set(pred_ans)) and ((len(pred_ans) > 0) or unanswerability): #TODO: for now we assume that semantically correct lf is equivalent to non-empty answer
                is_nl_semantic_issue = True
        if nl_semantic_feedback and nl_semantic_feedback_mode == 'always':
            gt_ans = [ans['answer_argument'] for ans  in question['answer']]
            is_nl_semantic_issue = (len(pred_ans) > 0) or unanswerability
        if nl_semantic_feedback and nl_semantic_feedback_mode == 'gpt_feedback':
            query_we_answer = naturalize_query(pred_lf)
            is_nl_semantic_issue = not (get_gpt_feedback(query_we_answer, question['question'], nl_semantic_feedback_prompt, '|query|'+retriever_augmented_test_data[str(question['qid'])]['input_seq'].split('|query|')[-1])) #TODO: check this!!
        if not nl_semantic_feedback:
            query_we_answer = pred_lf
        gt_ans = [ans['answer_argument'] for ans  in question['answer']]
        log_dict['is_nl_semantic_issue'] = is_nl_semantic_issue
        is_intermediate_node = is_type_node(pred_ans) and cvt_feedback 
        log_dict['is_intermediate_node'] = is_intermediate_node
        if lf_semantic_feedback and (pred_ans == [] or pred_ans == ['0']):
            semantic_feedback = check_type(pred_lf)
            if semantic_feedback != 'correct':
                is_semantic_issue = True
            else:
                is_semantic_issue = False
        else:
            is_semantic_issue = False
        log_dict['is_lf_semantic_issue'] = is_semantic_issue
        pred_lf_choices: List[dict] = [] # for algos that rely on multiple lf choices
        is_validator_happy = True
        all_feedbacks = []
        if ((len(pred_ans) == 0 ) or is_intermediate_node or is_semantic_issue or is_nl_semantic_issue or is_grounding_issue or is_float_suffix_issue or is_qans_issue or is_mult_issue) and pred_lf != 'NK': #TODO: pls add `and not unanswerability` ASAP!!
            is_validator_happy = False
            while num_retries:
                if is_grounding_issue:# grounding issue is most major!
                    prompt = construct_grounding_prompt(prompt, pred_lf, program_lang,  grounded_feedback)
                    logging.info('grounding issue detected!!')
                    latest_prompt = 'grounding'
                    all_feedbacks.append(latest_prompt)
                elif is_qans_issue:
                    prompt = construct_qans_prompt(prompt, pred_lf, program_lang, mid_to_friendly(':'+pred_ans[0]))
                    logging.info('QAns issue detected!!')
                    latest_prompt = 'qans'
                    all_feedbacks.append(latest_prompt)
                elif is_mult_issue:
                    prompt = construct_mult_prompt(prompt, pred_lf, program_lang)
                    logging.info('Multiple answers issue detected!!')
                    # print('Multiple answers issue detected!!')
                    latest_prompt = 'mult'
                    all_feedbacks.append(latest_prompt)
                elif is_float_suffix_issue: # pls add the float suffix
                    prompt = construct_float_suffix_prompt(prompt, pred_lf, program_lang)
                    logging.info('float suffix issue detected!!')
                    latest_prompt = 'float_suffix'
                    all_feedbacks.append(latest_prompt)
                # if (len(pred_ans) > 0) and cvt_feedback and not(is_nl_semantic_issue): #only intermediate issue #TODO: literals returned are not cvts!!!
                elif is_intermediate_node:
                    prompt = construct_intermediate_prompt(prompt, pred_lf, program_lang)
                    latest_prompt = 'intermediate'
                    all_feedbacks.append(latest_prompt)
                elif is_semantic_issue: # logical form semantic issue
                    semantic_feedback = check_type(pred_lf)
                    prompt = construct_lf_semantic_feedback_prompt(prompt, pred_lf, program_lang, semantic_feedback)
                    latest_prompt = 'lf_semantic'
                    all_feedbacks.append(latest_prompt)
                elif is_nl_semantic_issue: # natural language semantic issue
                    logger.info('NL semantic issue detected !!')
                    #TODO: check this!!!
                    prompt, query_we_answer = construct_nl_semantic_feedback_prompt(prompt, pred_lf, program_lang, question['question'])
                    pred_lf_choices.append({'pred_lf': pred_lf, 'pred_nl': query_we_answer, 'pred_ans': pred_ans, 'nl_semantic_check': False})
                    latest_prompt = 'nl_semantic'
                    all_feedbacks.append(latest_prompt)
                elif pred_ans == []: 
                    prompt = construct_egf_prompt(prompt, pred_lf, program_lang)
                    pred_lf_choices.append({'pred_lf': pred_lf, 'pred_nl': query_we_answer, 'pred_ans': pred_ans, 'nl_semantic_check': True})
                    latest_prompt = 'egf'
                    all_feedbacks.append(latest_prompt)
                else:
                    logger.info('no new prompt...nothing further to try')
                    num_retries = 0
                pred_lf = ask_gpt_anything(prompt)
                if '{' not in pred_lf:
                    # probably an error message returned by gpt...
                    pred_lf = 'NK'
                if pred_lf == 'NK':
                    break
                if 'LIMIT 1' in pred_lf and not('MAX' in pred_lf or 'MIN' in pred_lf or 'GROUP BY' in pred_lf or 'ORDER BY' in pred_lf):
                    logger.info('singular plural issue detected! removing unnecessary constraint...')
                    logger.info(pred_lf)
                    pred_lf = pred_lf.replace('LIMIT 1', '')
                pred_ans = get_answer(pred_lf, syntax_feedback)
                if pred_ans != []:
                    if pred_ans[0] == 'syntax_error':
                        pred_lf = correct_syntax(pred_lf, pred_ans[1])
                        pred_ans = get_answer(pred_lf, syntax_feedback)
                        if pred_ans != []:
                            if pred_ans[0] == 'syntax_error': # we conuldn't correct the error despite efforts
                                pred_ans = []
                if pred_ans == ['nonsense']:
                    break
                if ((pred_ans == ['0']) and not unanswerability):
                    pred_ans = [] # getting answer '0' (for a count question) means that the answer is empty
                is_intermediate_node = is_type_node(pred_ans) and cvt_feedback
                is_semantic_issue = (len(pred_ans) == 0 or pred_ans == ['0']) and (check_type(pred_lf) != 'correct') and lf_semantic_feedback
                if nl_semantic_feedback_mode == 'gt':
                    is_nl_semantic_issue = ((len(pred_ans) > 0) or unanswerability) and (set(gt_ans) != set(pred_ans)) and nl_semantic_feedback#TODO: len(pred_ans) cond only for answerable
                elif nl_semantic_feedback_mode == 'always':
                    is_nl_semantic_issue = ((len(pred_ans) > 0) or unanswerability)  and nl_semantic_feedback
                elif nl_semantic_feedback_mode == 'gpt_feedback':
                    query_we_answer = naturalize_query(pred_lf)
                    is_nl_semantic_issue = ((len(pred_ans) > 0)or unanswerability)  and nl_semantic_feedback and not (get_gpt_feedback(query_we_answer, question['question'], nl_semantic_feedback_prompt,  '|query|'+retriever_augmented_test_data[str(question['qid'])]['input_seq'].split('|query|')[-1]))
                elif not nl_semantic_feedback:
                    query_we_answer = pred_lf
                grounded_feedback = get_grounded(pred_lf, str(question['qid']), retriever_augmented_test_data)
                if grounded_feedback != 'correct':
                    is_grounding_issue = True
                else:
                    is_grounding_issue = False
                if (len(pred_ans) == 1):
                    if pred_ans[0] in topic_entity_nodes: 
                        is_qans_issue = True
                    else:
                        is_qans_issue = False
                else:
                    is_qans_issue = False
                if (len(pred_ans) == 1):
                    if pred_ans[0] == 'multiple_vars': 
                        is_mult_issue = True
                    else:
                        is_mult_issue = False
                else:
                    is_mult_issue = False
                if (('>=' in pred_lf or '<=' in pred_lf or ' > ' in pred_lf or ' < ' in pred_lf) and ('<http://www.w3.org/2001/XMLSchema#float>' not in pred_lf) and ('^^xsd:dateTime' not in pred_lf)): #TODO: ensure it isn't datetime as well!!
                    is_float_suffix_issue = True 
                else:
                    is_float_suffix_issue = False
                
                logger.info(f'pred_ans: {pred_ans}')
                if (not is_semantic_issue):
                        best_ans = pred_ans
                        best_lf = pred_lf
                if ((len(pred_ans) > 0)) and (not(is_intermediate_node)) and (not(is_semantic_issue)) and (not(is_nl_semantic_issue) and (not(is_qans_issue)) and (not(is_mult_issue))):#TODO: pls add  `or unanswerability` ASAP!!!!
                    logger.info('egf at work!')
                    is_validator_happy = True
                    logger.info(f'pred_ans: {pred_ans}')
                    break
                num_retries -= 1
        else:
            is_validator_happy = True
        if nl_semantic_feedback_mode == 'always' or nl_semantic_feedback_mode == 'gpt_feedback':
            if (pred_lf == 'NK'):
                best_lf = 'NK'
                best_ans = []
            if (pred_ans != [] or unanswerability):
                prompt, query_we_answer = construct_nl_semantic_feedback_prompt(prompt, pred_lf, program_lang, question['question'])
                if not(is_semantic_issue) and not(is_mult_issue) and not(is_float_suffix_issue) and not(is_grounding_issue) and not(is_qans_issue) and not(is_intermediate_node):
                    pred_lf_choices.append({'pred_lf': pred_lf, 'pred_nl': query_we_answer, 'pred_ans': pred_ans, 'nl_semantic_check': not (is_nl_semantic_issue)})
            if (not is_validator_happy )and (pred_lf != 'NK'):
                best_lf, best_ans = select_best_lf(pred_lf_choices, question['question'], nl_semantic_feedback_mode, unanswerability) #TODO: check this!!
            if (not is_validator_happy) and unanswerability:
                # logger.info('validator aint happy and we live in unanswerable world')
                # best_lf = 'NK'
                # best_ans = []
                if best_lf == 'NK':
                    logger.info('validator aint happy and we live in unanswerable world -- schema level unanswerable')
                elif best_ans != []:
                    logger.info('super self consistency')
                else:
                    logger.info('data level unanswerable')
        logger.info(f'pred_ans: {pred_ans}')
        best_ans_final = [b for b in best_ans if b not in topic_entity_nodes]
        best_ans = best_ans_final
        logger.info(f'best_ans: {best_ans}') #TODO: maybe have a better algo for selecting the best answer
        logger.info(f'gt ans: {gt_ans}')
        logger.info(f'latest prompt: {latest_prompt}')
        logger.info(f'total retries: {stt_num_retries - num_retries}')
        if pred_lf == 'NK':
            is_validator_happy = True
        logger.info(f'---report: {question["qid"]}---\nans match: {set(gt_ans) == set(best_ans)}\nconfident:{is_validator_happy}\ngtype: {"K" if question["s_expression"]!= "NK" else "NK"}\nptype: {"K" if get_grounded(question["sparql_query"], str(question["qid"]), retriever_augmented_test_data)=="correct" else "NK"}\nall prompts: {all_feedbacks}')

        test_data[idx]['pred_lf'] = best_lf
        test_data[idx]['pred_ans'] = best_ans
        dump_json(test_data[:idx+1], os.path.join(output_dir, prediction_dump_file))


if __name__ == '__main__':
    # select_best_choice()
    # sys.exit(0)
    config_file = sys.argv[1]
    config = load_json(config_file)
    program_lang = config['program_lang'] 
    input_train_file = config['input_train_file']
    input_test_file = config['input_test_file']
    train_data = load_json(input_train_file)
    test_data = load_json(input_test_file)
    logging.getLogger().setLevel(logging.INFO)
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                        level=logging.INFO,
                        datefmt='%Y-%m-%d %H:%M:%S',
                        filename=f"./logs/{os.path.basename(input_train_file)}____{os.path.basename(input_test_file)}_{str(datetime.datetime.now()).replace(' ', '_')}.log"
                        )
    logger = logging.getLogger(__name__)
    logger.info("**execution begins**")
    if 'start_idx' in config and 'stop_idx' in config: 
        test_data = test_data[config['start_idx']: config['stop_idx']]
    elif 'start_idx' in config:
        test_data = test_data[config['start_idx']:]
    if 'subset_test' in config:
        test_data = get_subset(test_data, config['subset_test'])
    retriever_augmented_train = config['retriever_augmented_train_file']
    retriever_augmented_test = config['retriever_augmented_test_file']
    if 'func_predictions_test' in config:
        func_predictions_test = config['func_predictions_test']
    else:
        func_predictions_test = None
    num_retries = config['num_retries']
    exemplar_selection = config['exemplar_selection']
    num_shots = config['num_shots']
    output_dir = config['output_dir']
    naturalize_varnames = config['naturalize_varnames']
    syntax_feedback = config['syntax_feedback']
    lf_semantic_feedback = config['lf_semantic_feedback']    
    cvt_feedback = config['cvt_feedback']
    nl_semantic_feedback = config['nl_semantic_feedback']
    if nl_semantic_feedback:
        nl_semantic_feedback_mode = config['nl_semantic_feedback_mode']
        if nl_semantic_feedback_mode == 'gpt_feedback':
            nl_semantic_feedback_prompt = open(config['nl_semantic_feedback_prompt_file']).read()
        else:
            nl_semantic_feedback_prompt = 'none'
    else:
        nl_semantic_feedback_mode = 'none'
        nl_semantic_feedback_prompt = 'none'
    if 'unanswerability' in config:
        unanswerability = config['unanswerability']
    else:
        unanswerability = False
    logger.info(config)
    # gen_query(train_data, test_data, retriever_augmented_train, retriever_augmented_test, func_predictions_test, num_retries, exemplar_selection, num_shots, output_dir, program_lang, naturalize_varnames, syntax_feedback, lf_semantic_feedback, cvt_feedback, nl_semantic_feedback, nl_semantic_feedback_mode, nl_semantic_feedback_prompt, unanswerability, logger=logger)
    # gen_initial_batch(train_data, test_data, retriever_augmented_train, retriever_augmented_test, func_predictions_test, num_retries, exemplar_selection, num_shots, output_dir, program_lang, naturalize_varnames, syntax_feedback, lf_semantic_feedback, cvt_feedback, nl_semantic_feedback, nl_semantic_feedback_mode, nl_semantic_feedback_prompt, unanswerability)
    gen_query_batch(train_data, test_data, retriever_augmented_train, retriever_augmented_test, func_predictions_test, num_retries, exemplar_selection, num_shots, output_dir, program_lang, naturalize_varnames, syntax_feedback, lf_semantic_feedback, cvt_feedback, nl_semantic_feedback, nl_semantic_feedback_mode, nl_semantic_feedback_prompt, unanswerability)
    
#TODO:
# apologizes once, tell it to think harder!

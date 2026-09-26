import utils
import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)

def constant_prompt(): 
    '''
    returns a handrafted prompt with better varnames
    '''
    with open('constant.txt') as f:
        prompt = f.read()
    return prompt

def construct_sub_prompt(question: str, cand_entities: str, cand_paths: str, cand_classes: str, cand_rels: str, program_lang : str, program: str = '', naturalize_varnames: bool = False) -> str:
    '''
    construct the sub prompt using question, cand_entities, cand_paths, cand_classes, cand_rels
    '''
    ques_line = f'Question: {question}\n'
    if 'm.' not in cand_entities and 'g.' not in cand_entities:
        cand_entities = 'NONE'
    cand_entities_line = f'Candidate entities: {(cand_entities)}\n'
    cand_paths_line = f'Candidate paths: {"|".join(cand_paths.split("|")[:5])}\n'
    cand_classes_line = f'Candidate entity types: ns:{"|ns:".join(cand_classes.split("|")[:10])}\n'
    cand_rels_line = f'Candidate relations: {"|ns:".join(cand_rels.split("|")[:10])}\n'
    if naturalize_varnames:
        program = utils.naturalize_varnames(program)
    if 'http' not in program:
        program = utils.sexp_to_sparql(program)
    prompt = ques_line + cand_entities_line + cand_paths_line + cand_classes_line + cand_rels_line + f'{program_lang}:{program}\n'
    return prompt

def construct_sub_prompt_ensemble(mode: str, question: str, cand_entities: str, cand_paths_tiara: str, cand_paths_pangu: str, cand_classes_tiara: str, cand_classes_pangu: str, cand_rels_tiara: str, cand_rels_pangu: str, program_lang : str, program: str = '', naturalize_varnames: bool = False) -> str:
    #TODO: remove slicing from input
    '''
    construct the sub prompt using question, cand_entities, cand_paths, cand_classes, cand_rels for an ensemble of retrievers
    '''
    if mode == 'train':
        num_paths = 3
        num_classes = 5
        num_rels = 5
    elif mode == 'test':
        num_paths = 5
        num_classes = 10
        num_rels = 10
    ques_line = f'Question: {question}\n'
    if 'm.' not in cand_entities and 'g.' not in cand_entities:
        cand_entities = 'NONE'
    cand_entities_line = f'Candidate entities: {(cand_entities)}\n'
    cand_paths_line_1 = f'Candidate paths from Retriever 1: {"|".join(cand_paths_tiara.split("|")[:num_paths])}\n'
    cand_paths_line_2 = f'Candidate paths from Retriever 2: {"|".join(cand_paths_pangu.split("|")[:num_paths])}\n'
    cand_classes_line_1 = f'Candidate entity types from Retriever 1: ns:{"|ns:".join(cand_classes_tiara.split("|")[:num_classes])}\n'
    cand_classes_line_2 = f'Candidate entity types from Retriever 2: ns:{"|ns:".join(cand_classes_pangu.split("|")[:num_classes])}\n'
    cand_rels_line_1 = f'Candidate relations from Retriever 1: ns:{"|ns:".join(cand_rels_tiara.split("|")[:num_rels])}\n'
    cand_rels_line_2 = f'Candidate relations from Retriever 2: ns:{"|ns:".join(cand_rels_pangu.split("|")[:num_rels])}\n'
    if naturalize_varnames:
        program = utils.naturalize_varnames(program)
    if 'http' not in program:
        program = utils.sexp_to_sparql(program)
    prompt = ques_line + cand_entities_line + cand_paths_line_1 + cand_paths_line_2 + cand_classes_line_1 + cand_classes_line_2 + cand_rels_line_1 + cand_rels_line_2 + f'{program_lang}:{program}\n'
    return prompt

def construct_prompt(exemplars: List[str], test_qn: str, train_data, retriever_augmented_train_data, retriever_augmented_test_data, program_lang : str, naturalize_varnames: bool = False, unanswerability: bool = False) -> List[dict]:
    '''
    construct the prompt using exemplar qids and test qn qid
    '''
    intro = f'''Translate the following question to {program_lang} for Freebase based on the candidate {program_lang}, candidate entities, candidate relations and candidate entity types which are separated by "|" respectively. Please do not include any other relations, entities and entity types. \nYour final {program_lang} can have three scenarios: \n1. When you need to just pick from candidate sparql. \n2. When you need to extend one of candidate {program_lang} using the candidate relations and entity types. \n3. When you will generate a new {program_lang} only using the candidate entities, relations and entity types.\nFor  entity type check please use this relation \"type.object.type\".\n'''
    # if unanswerability:
    # TODO: remove this!!!
    #   intro += 'If it is impossible to construct a query using the provided candidate relations or types, return "NK".'
    # TODO: asap asap asap 
    intro +='Do not use entity names in the query. Use only specified mids mentioned at "Candidate entities".\n'
    back_trans_prompt = 'Do not use "UNION" in the query.Make sure that the original question can be regenerated only using the identified entity types, specific entities and relations.\n'
    prompt_header = f'{intro}{back_trans_prompt}'
    exemplar_prompts = []
    if program_lang == 'sparql':
        program_lang_field = 'sparql_query'
    else:
        program_lang_field = program_lang
    if unanswerability: # or 1 #TODO add this asap asap asap 
        program_lang_field = 's_expression'
    for exemplar_qid in exemplars: 
        for i in range(len(train_data)):
            if str(train_data[i]['qid']) == exemplar_qid:
                program = train_data[i][f'{program_lang_field}']
                # #TODO: remove this
                # if train_data[i][f's_expression'] == 'NK':
                #     program = 'NK'
                # else:
                #     program = train_data[i]['sparql_query']
                # #TODO ends asap asap asap!!!
                break
        if 'tiara' in retriever_augmented_train_data:
            retrieved_data_tiara = retriever_augmented_train_data['tiara'][exemplar_qid]['input_seq'] 
            retrieved_data_pangu = retriever_augmented_train_data['pangu'][exemplar_qid]['input_seq'] 
            ques, cand_entities, cand_classes_tiara, cand_paths_tiara, cand_rels_tiara = utils.process_retriever_op(retrieved_data_tiara)
            ques, cand_entities, cand_classes_pangu, cand_paths_pangu, cand_rels_pangu = utils.process_retriever_op(retrieved_data_pangu)
            cand_rels_tiara, list_of_rels_tiara = utils.simplify_cand_rels(cand_rels_tiara)
            cand_rels_pangu, list_of_rels_pangu = utils.simplify_cand_rels(cand_rels_pangu)
            if program_lang == 'sparql':
                cand_paths_tiara = utils.simplify_cand_paths(utils.sexp_to_sparql(cand_paths_tiara), list_of_rels_tiara) 
                cand_paths_pangu = utils.simplify_cand_paths(utils.sexp_to_sparql(cand_paths_pangu), list_of_rels_pangu) 
                if unanswerability: #dataset has wrong sparqls, so we translate the sexpressions instead
                    program = utils.sexp_to_sparql(program)  
            sub_prompt = construct_sub_prompt_ensemble('train', ques, cand_entities, cand_paths_tiara, cand_paths_pangu, cand_classes_tiara, cand_classes_pangu, cand_rels_tiara, cand_rels_pangu, program_lang, program, naturalize_varnames)
        else:
            retrieved_data = retriever_augmented_train_data[exemplar_qid]['input_seq']        
            ques, cand_entities, cand_classes, cand_paths, cand_rels = utils.process_retriever_op(retrieved_data)
            cand_rels, list_of_rels = utils.simplify_cand_rels(cand_rels)
            if program_lang == 'sparql':
                cand_paths = utils.simplify_cand_paths(utils.sexp_to_sparql(cand_paths), list_of_rels)   
                if unanswerability: #dataset has wrong sparqls, so we translate the sexpressions instead
                    program = utils.sexp_to_sparql(program)     
            sub_prompt = construct_sub_prompt(ques, cand_entities, cand_paths, cand_classes, cand_rels, program_lang, program, naturalize_varnames)
        
        
        exemplar_prompts.append(sub_prompt)
    exemplar_prompt = '\n'.join(exemplar_prompts)
    if 'tiara' in retriever_augmented_test_data:
        # DO SOMETHING HERE!!
        retrieved_data_tiara = retriever_augmented_test_data['tiara'][test_qn]['input_seq']
        retrieved_data_pangu = retriever_augmented_test_data['pangu'][test_qn]['input_seq']
        ques, cand_entities, cand_classes_tiara, cand_paths_tiara, cand_rels_tiara = utils.process_retriever_op(retrieved_data_tiara)
        ques, cand_entities, cand_classes_pangu, cand_paths_pangu, cand_rels_pangu = utils.process_retriever_op(retrieved_data_pangu)
        cand_rels_tiara, list_of_rels_tiara = utils.simplify_cand_rels(cand_rels_tiara)
        cand_rels_pangu, list_of_rels_pangu = utils.simplify_cand_rels(cand_rels_pangu)
        if program_lang == 'sparql':
            cand_paths_tiara = utils.simplify_cand_paths(utils.sexp_to_sparql(cand_paths_tiara), list_of_rels_tiara)
            cand_paths_pangu = utils.simplify_cand_paths(utils.sexp_to_sparql(cand_paths_pangu), list_of_rels_pangu)
        sub_prompt = construct_sub_prompt_ensemble('test', ques, cand_entities, cand_paths_tiara, cand_paths_pangu, cand_classes_tiara, cand_classes_pangu, cand_rels_tiara, cand_classes_pangu, program_lang)    
    else: 
        retrieved_data = retriever_augmented_test_data[test_qn]['input_seq']
        ques, cand_entities, cand_classes, cand_paths, cand_rels = utils.process_retriever_op(retrieved_data)
        cand_rels, list_of_rels = utils.simplify_cand_rels(cand_rels)
        if program_lang == 'sparql':
            cand_paths = utils.simplify_cand_paths(utils.sexp_to_sparql(cand_paths), list_of_rels)
        sub_prompt = construct_sub_prompt(ques, cand_entities, cand_paths, cand_classes, cand_rels, program_lang)
    if len(exemplars) == 0:
        # exemplar_prompt = constant_prompt()
        exemplar_prompt = ''
    # prompt = prompt_header + exemplar_prompt + sub_prompt
    prompt = []
    prompt.append({"role": "system", "content": prompt_header})
    prompt.append({"role": "user", "content": exemplar_prompt+sub_prompt})
    return prompt

def construct_egf_prompt(prompt: List[dict], pred_lf: str, program_lang: str) -> List[dict]:
    '''
    returns the prompts that should be used as further downstream in case of empty answer
    '''
    prompt.append({"role": "assistant", "content": pred_lf})
    empty_answer_feedback_prompt = f'The generated {program_lang} gives an empty answer when executed on freebase KG, Please generate again a different executable {program_lang} using the same context and constraints.\n{program_lang}:'
    prompt.append({"role": "user", "content": empty_answer_feedback_prompt})
    return prompt

def construct_intermediate_prompt(prompt: List[dict], pred_lf: str, program_lang: str) -> List[dict]:
    '''
    providing feedback that the nodes returned are intermediate nodes in the graph
    & they dont correspond to any real world entity/literal
    '''
    prompt.append({"role": "assistant", "content": pred_lf})
    intermediate_node_feedback_prompt = f'The generated {program_lang} returns an intermediate type node when executed on the freebase KG. Maybe the answer node is an adjacent node to what we currently query for. Please generate again a different executable {program_lang} using the same context and constraints.\n{program_lang}:'
    prompt.append({"role": "user", "content": intermediate_node_feedback_prompt})
    return prompt


def construct_lf_semantic_feedback_prompt(prompt: List[dict], pred_lf: str, program_lang: str, semantic_feedback: str):
    '''
    we identify that the types of entities in the constructed lf are not coherent
    provide feedback to gpt-4 to self correct
    '''
    prompt.append({"role": "assistant", "content": pred_lf})
    semantic_feedback_prompt = f'The generated {program_lang} has a semantic issue warning: {semantic_feedback}. Please generate again a different executable {program_lang} using the same context and constraints. DO NOT APOLOGIZE - just return the best you can try.\n{program_lang}:'
    prompt.append({"role": "user", "content": semantic_feedback_prompt})
    return prompt

def get_mention(exemplars: List[str], retriever_augmented_train_data, test_qn) -> str:
    '''
    few shot llm prompting for detecting the mentions
    '''
    sys_prompt = "Please identify the mentions in the following text: \n"
    prompt: List[dict] = []
    prompt.append({"role": "system", "content": sys_prompt})
    for exemplar_qid in exemplars:
        retrieved_data = retriever_augmented_train_data[exemplar_qid]['input_seq']
        ques, cand_entities, cand_classes, cand_paths, cand_rels = utils.process_retriever_op(retrieved_data)
        ents = cand_entities.split("|")
        mention = ""
        for ent in ents:
            mention += ' '.join(ent.split(' ')[:-1]) + ' '
        prompt.append({"role": "user", "content": ques})
        prompt.append({"role": "assistant", "content": mention})
    prompt.append({"role": "user", "content": test_qn})
    mention = utils.ask_gpt_anything(prompt)
    return mention

def naturalize_varnames(sparql_query: str)-> str:
    '''
    :param sparql_query: sparql query with varnames like ?x, ?y or whatever
    :return: sparql query with varnames like ?country, ?person
    '''
    # step1: if any mids occur, make them VALUES ?m1 {<mid1> } and so on
    # traverse the sparql query and find all the mids
    # words = sparql_query.split()
    # mids = []
    # for word in words:
    #     # get count of '.'
    #     count = word.count('.')
    #     if count == 1 and ('m.' in word or 'g.' in word):
    #         mids.append(word)
    # for idx, mid in enumerate(mids):
    #     sparql_query = sparql_query.replace(mid, f'?m{idx}')
    #     # sparql_query = re.sub(r'DISTINCT\s*?[a-zA-Z0-9]+\s*WHERE\s*{\s*', 'WHERE {\n'+f'VALUES ?m{idx} {{{mid}}}', sparql_query, count=1)
    #     sparql_query = re.sub(r'(DISTINCT\s*?[a-zA-Z0-9]+)\s*WHERE\s*{\s*', r'\1 WHERE {\n'+f'VALUES ?m{idx} {{{mid}}}', sparql_query, count=1)
    # step2: replace all the ?x, ?y with ?country, ?person and so on
    sys_prompt = "change the sparql query to have variable names representative of what objects thet refer to. transform the variable names in this query. Do NOT change the prefix headers and relation names"
    usr_prompt = sparql_query
    prompt = []
    prompt.append({"role": "system", "content": sys_prompt})
    prompt.append({"role": "user", "content": usr_prompt})
    new_sparql_query = utils.ask_gpt_anything(prompt)
    return new_sparql_query


def construct_nl_semantic_feedback_prompt(prompt: List[dict], pred_lf: str, program_lang: str, orig_nl_question: str) -> Tuple[List[dict], str]:
    '''
    providing feedback that the question that we answer via pred_lf is not equivalent to the original question

    '''
    prompt.append({"role": "assistant", "content": pred_lf})
    query_we_answer = utils.naturalize_query(pred_lf)
    #TODO: apologizing might be favourable in non-gt mode -- look into this. 
    # semantic_equivalence_feedback_prompt = f'The question that you answer is NOT same as what you\'ve been asked for! You have answered the question \"{query_we_answer}\" but you were asked to answer \"{orig_nl_question}\". Please generate again a different executable {program_lang} using the relations, classes and paths provided earlier. DO NOT APOLOGIZE - just return the best you can try. \n{program_lang}:'
    semantic_equivalence_feedback_prompt = f'The question that you answer is NOT same as what you\'ve been asked for! You have answered the question \"{query_we_answer}\" but you were asked to answer \"{orig_nl_question}\". Please generate again a different executable {program_lang} using the relations, classes and entities provided earlier. Assume that relations, classes and entities provided are suffient to construct the query. You are allowed to use any {program_lang} in-built query construct as required.  DO NOT APOLOGIZE - just return the best you can try. \n{program_lang}:'
    prompt.append({"role": "user", "content": semantic_equivalence_feedback_prompt})
    return prompt, query_we_answer

def construct_grounding_prompt(prompt: List[dict], pred_lf: str, program_lang: str, grounded_feedback: str) -> List[dict]:
    '''
    providing feedback that the schema elements used don't exist in the KG

    '''
    prompt.append({"role": "assistant", "content": pred_lf})
    grounding_feedback_prompt = f'The generated {program_lang} does not used the retrieved elements shared: {grounded_feedback}. Please generate again a different executable {program_lang} using ONLY those schema elements that have been provided.\n{program_lang}:'
    prompt.append({"role": "user", "content": grounding_feedback_prompt})
    return prompt

def construct_float_suffix_prompt(prompt: List[dict], pred_lf: str, program_lang: str) -> List[dict]:
    '''
    freebase required all float numbers to end with the float suffix. 
    '''
    prompt.append({"role": "assistant", "content": pred_lf})
    float_suffix_prompt = 'Please ensure that all numeric values are placed in double quotes and end with the \"^^<http://www.w3.org/2001/XMLSchema#float>\" suffix for correct numerical computations. eg: \"10\"^^<http://www.w3.org/2001/XMLSchema#float>'
    prompt.append({"role": "user", "content": float_suffix_prompt})
    return prompt

def construct_qans_prompt(prompt: List[dict], pred_lf: str, program_lang: str, topic_entity_node: str) -> List[dict]:
    '''
    if the answer is same as the topic entity in the question, there is definetely some issue!
    '''
    prompt.append({"role": "assistant", "content": pred_lf})
    qans_prompt = f'The logical form upon execution returns {topic_entity_node}, which is not answering the question. Please reconstruct the query using same context'
    prompt.append({"role": "user", "content": qans_prompt})
    return prompt

def construct_mult_prompt(prompt: List[dict], pred_lf: str, program_lang: str) -> List[dict]:
    '''
    if the query upon execution returns values corresponding to multiple variables, this is not expected behaviour!
    '''
    prompt.append({"role": "assistant", "content": pred_lf})
    mult_prompt = f'The logical form queries to obtain values for multiple variables. Hoewver, we expect the query to only return one variable. Please reconstruct the query using same context'
    prompt.append({"role": "user", "content": mult_prompt})
    return prompt

if __name__ == '__main__':
    import ipdb; ipdb.set_trace()
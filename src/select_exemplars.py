import random
random.seed(100)
from utils import load_json, process_retriever_op, check_retriever_correctness, ask_gpt_anything
from rank_bm25 import BM25Okapi
import spacy
from tqdm import tqdm
import os
import json
import logging
from typing import List
# from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

HTTP_PROXY = 'http://10.10.78.61:3128'
HTTPS_PROXY = 'http://10.10.78.61:3128'


def select_exemplars(train_data, retriever_augmented_train_data, exemplar_selection: str, num_shots: int, test_nl_qn: str = '')-> list:
    '''
    returns the qids of exemplars selected for few shot prompting
    '''
    correct_train_data = []
    for datapoint in train_data:
        gt_program = datapoint['sparql_query']
        retriever_op = retriever_augmented_train_data[str(datapoint['qid'])]['input_seq']
        ques, cand_entities, cand_classes, cand_paths, cand_rels = process_retriever_op(retriever_op)
        if check_retriever_correctness(cand_entities, cand_classes, cand_paths, cand_rels, gt_program):
            correct_train_data.append(datapoint)

    if exemplar_selection == 'random':
        return select_exemplars_random(train_data, num_shots)
    elif exemplar_selection == 'bert':
        return select_exemplars_bert()
    elif exemplar_selection == 'bm25':
        return select_exemplars_bm25()
    elif exemplar_selection == 'constant':
        return []
    elif exemplar_selection == 'gpt':
        return select_exemplars_gpt()
    elif exemplar_selection == 'bm25_gpt4':
        return select_exemplars_bm25_gpt4()
    elif exemplar_selection == 'cosine_similarity':
        return select_exemplars_cosine_similarity(train_data, num_shots, test_nl_qn)

def select_exemplars_random(train_data, num_shots: int)-> List[str]:
    random.seed(100)
    sample =  random.sample(train_data, num_shots)
    qids = []
    for s in sample:
        qids.append(str(s['qid']))
    return qids

def select_exemplars_bert(input_train_file: str, pred_fns_file: str, num_shots: int)-> list:
    train_data = load_json(input_train_file)
    pred_fns = load_json(pred_fns_file)
    #TODO -- will do later

def create_index(train_data,nlp_model):
    corpus = [data["question"] for data in train_data]
    qids = [data["qid"] for data in train_data]
    tokenized_train_data = []
    for doc in tqdm(corpus):
        nlp_doc = nlp_model(doc)
        tokenized_train_data.append([token.lemma_ for token in nlp_doc])
    bm25_train_full = BM25Okapi(tokenized_train_data)
    return corpus,bm25_train_full,qids


def select_exemplars_bm25(train_data, num_shots: int, test_nl_qn: str = '')-> list:
    spacy_model = spacy.load("en_core_web_sm")
    tokenized_query = spacy_model(test_nl_qn)
    corpus,bm25_train_full,qids=create_index(train_data,spacy_model)
    tokenized_query = [token.lemma_ for token in tokenized_query]
    top_ques = bm25_train_full.get_top_n(tokenized_query, corpus, n=num_shots)
    selected_examples = top_ques
    return selected_examples


def select_exemplars_gpt(train_data, num_shots: int, test_nl_qn: str = '')-> list:
    sys_prompt = f"Select {num_shots} closest question from the training list that can be selected for few shot semantic prompting\n. If none of the questions is close, randomly select the few shots"
    prompt = []
    prompt.append({"role": "user", "content": sys_prompt})
    usr_prompt = ''
    for idx, datapoint in enumerate(train_data):
        usr_prompt += f"{idx+1}. {datapoint['question']}\n"
    prompt.append({"role": "user", "content": usr_prompt + 'Test question: ' + test_nl_qn})
    logging.info(prompt)
    gpt_reply = ask_gpt_anything(prompt)
    logging.info('printing gpt_reply')
    logging.info(gpt_reply)
    exemplar_qids = []
    for datapoint in train_data:
        if (datapoint['question'] in gpt_reply) and (len(exemplar_qids) < num_shots):
            exemplar_qids.append(datapoint['qid'])
    return exemplar_qids

def select_exemplars_bm25_gpt4(train_data, num_shots: int, test_nl_qn: str = '')-> str:
    new_train_data = []
    # step1: select top 100 questions using bm25
    if len(train_data) > 100:
        exemplar_qids = select_exemplars_bm25(train_data, 100, test_nl_qn)
    for datapoint in train_data:
        if datapoint['qid'] in exemplar_qids:
            new_train_data.append(datapoint)
    # step2: select top 5 questions using gpt4
    exemplar_qids = select_exemplars_gpt(new_train_data, num_shots, test_nl_qn)
    return exemplar_qids

train_embeddings_1hop = None
train_embeddings_2hop = None
train_embeddings_3hop = None

def select_exemplars_cosine_similarity(train_data, num_shots: int, test_nl_qn: str):
    '''
    compute sentence embeddings of all qns in train_data and return <num_shos> no. 
    of qns that are closest to test_nl_qn
    '''
    train_data = [d for d in train_data if d['s_expression']!= 'NK']# considering the schema-level answerable qns only!!
    global train_embeddings_1hop
    global train_embeddings_2hop
    global train_embeddings_3hop 
    os.environ['http_proxy'] = HTTP_PROXY
    os.environ['https_proxy'] = HTTPS_PROXY
    model = SentenceTransformer('all-MiniLM-L6-v2')
    del os.environ['http_proxy']
    del os.environ['https_proxy']

    # Compute embeddings for train_data and test_nl_qn
    if train_embeddings_1hop is None:
        train_embeddings_1hop = model.encode([d['question'] for d in train_data if d['num_edge']==1], convert_to_tensor=True)
    if train_embeddings_2hop is None:
        train_embeddings_2hop = model.encode([d['question'] for d in train_data if d['num_edge']==2], convert_to_tensor=True)
    if train_embeddings_3hop is None:
        train_embeddings_3hop = model.encode([d['question'] for d in train_data if d['num_edge']>2], convert_to_tensor=True)
    test_embedding = model.encode([test_nl_qn], convert_to_tensor=True)

    logging.info(f'test nl qn is {test_nl_qn}')
    # Compute cosine similarity
    cos_similarities_1hop = cosine_similarity(test_embedding, train_embeddings_1hop)[0]
    cos_similarities_2hop = cosine_similarity(test_embedding, train_embeddings_2hop)[0]
    cos_similarities_3hop = cosine_similarity(test_embedding, train_embeddings_3hop)[0]
    # logging.info(f'cos_similarities are {cos_similarities}')


    # Get the indices of the most similar questions
    top_indices_1hop = np.argsort(cos_similarities_1hop)[-3:]#TODO: dont hard-code this stuff!!!
    top_indices_2hop = np.argsort(cos_similarities_2hop)[-1:]
    top_indices_3hop = np.argsort(cos_similarities_3hop)[-1:]

    qids = [str(train_data[i]['qid']) for i in top_indices_1hop]+[str(train_data[i]['qid']) for i in top_indices_2hop]+[str(train_data[i]['qid']) for i in top_indices_3hop]
    # Return the most similar questions
    return [qids[0], qids[3], qids[1], qids[4], qids[2]]

if __name__ == '__main__':
    import ipdb; ipdb.set_trace()
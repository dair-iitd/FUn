"""
given 2 datasets, compare their queries in terms of:
- #nodes
- #edges
- function
- #relation set
- #domain set
- nl qns
"""
import json
import os
from collections import Counter
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from gensim.corpora.dictionary import Dictionary
from gensim.models.ldamodel import LdaModel
from gensim.models.coherencemodel import CoherenceModel
from nltk.tokenize import word_tokenize
import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.spatial.distance import jensenshannon
import pandas as pd



DOMAIN_DICT = '../../data/freebase/domain_dict.json'
DOMAIN_DICT_LOADED = json.load(open(DOMAIN_DICT))

RELATIONS = '../../data/freebase/fb_roles.txt'
reln_to_type_map = {} 

# Open the file and read it line by line
with open(RELATIONS, 'r') as f:
    for line in f:
        # Split the line into parts
        parts = line.strip().split()

        # The relation is the second part, and the types are the first and third parts
        relation = parts[1]
        types = (parts[0], parts[2])

        # Add the relation and types to the mapping
        reln_to_type_map[relation] = types



DATASET1 = '../../data/100_data/grailqa_v1.0_train.json'
DATASET2 = '../../data/webqsp/webqsp_0107.test500.json'

HTTP_PROXY = '10.10.78.22:3128'
HTTPS_PROXY = '10.10.78.22:3128'

def get_types(rels_list):
    types_list = []
    for rel in rels_list:
        if rel in reln_to_type_map:
            types_list += reln_to_type_map[rel]
    return types_list

def get_rels(item):
    rels = []
    for edge in item['graph_query']['edges']:
        rels.append(edge['relation'])
    return rels

def get_entities(item):
    ents = []
    for edge in item['graph_query']['nodes']:
        ents.append(edge['id'])
    return ents

def get_domains(item):  
    domain_to_rel = DOMAIN_DICT_LOADED
    # domain_to_rel is str-> list of str, rel_to_domain is str->str
    rel_to_domain = {rel: domain for domain, rels in domain_to_rel.items() for rel in rels}
    domains = []
    for edge in item['graph_query']['edges']:
        domains.append(rel_to_domain[edge['relation']] if edge['relation'] in rel_to_domain else None)
    return domains

def get_skeleton(s_expr, dataset):
    if s_expr is None:
        return ''
    s_expr = s_expr.replace('(', ' ( ').replace(')', ' ) ')
    new_s_expr = ''
    for word in s_expr.split(): 
        if word in ['(', ')', 'JOIN', 'R', 'ARGMIN', 'ARGMAX', 'COUNT', 'TC', 'AND', '>=', '<=', '>', '<']:
            new_s_expr+= word
        else:
            new_s_expr += ' * '
    if new_s_expr.startswith('(AND * ') and new_s_expr.endswith(')') and ('grailqa' in dataset or 'graphqa' in dataset):
        new_s_expr = new_s_expr[7:]
        new_s_expr = new_s_expr[:-1]
    return new_s_expr

def get_corr_series(s1, s2):
    """
    s1 and s2 are unordered series of observations. 
    we take the frequency of each distinct item in the series and then return
    the correlation between the frequency distributions of the two series.
    """
    from scipy.stats import pearsonr
    from collections import Counter
    c1 = Counter(s1)
    c2 = Counter(s2)
    all_keys = set(c1.keys()).union(set(c2.keys()))
    freq1 = [c1[key] for key in all_keys]
    freq2 = [c2[key] for key in all_keys]
    # print(all_keys)
    # print('freq1:', freq1)
    # print('freq2:', freq2)
    if len(freq1) < 100:
        print(all_keys)
        print('series 1: ', freq1)
        print('series 2: ', freq2)
    return pearsonr(freq1, freq2)

def get_new_perc(s1, s2):
    """
    s1 and s2 are unordered series of observations. 
    we take the frequency of each distinct item in the series and then return
    the percentage of items in s2 that are not in s1.
    """
    c1 = Counter(s1)
    c2 = Counter(s2)
    all_keys = set(c1.keys()).union(set(c2.keys()))
    freq1 = [c1[key] for key in all_keys]
    freq2 = [c2[key] for key in all_keys]
    new_freq = [f2 for f1, f2 in zip(freq1, freq2) if f1==0]
    return sum(new_freq)/sum(freq2)

def get_new_perc_qns(ll1, s2):
    """
    percentage of questions in ll1 that are unseen in s2
    """
    num = 0
    tot = 0
    for qn_items_list in ll1:
        tot+=1
        if (any([qn_item not in s2 for qn_item in qn_items_list])):
            num+=1
    return num/tot


def get_kl_div(s1, s2):
    """
    returns KL-div P=s1, Q=s2
    """
    c1 = Counter(s1)
    c2 = Counter(s2)

    # Calculating the union of all keys
    all_keys = set(c1.keys()).union(set(c2.keys()))

    # Converting frequencies to probabilities
    total1 = sum(c1.values())
    total2 = sum(c2.values())
    prob1 = [c1[key] / total1 for key in all_keys]
    prob2 = [c2[key] / total2 for key in all_keys]

    # Adding a very small value to avoid division by zero or log(0) in KL divergence calculation
    epsilon = 1e-10
    prob1 = [p if p > 0 else epsilon for p in prob1]
    prob2 = [p if p > 0 else epsilon for p in prob2]

    # Calculating KL divergence
    kl_divergence = sum(p * np.log(p / q) for p, q in zip(prob1, prob2))

    return kl_divergence


def get_js_div(s1, s2):
    """
    returns jensen-shannon divergence
    JS-div considers the mean distribution and finds the KL-div of both series wrt mean. 
    symmetric measure
    """
    c1 = Counter(s1)
    c2 = Counter(s2)

    # Calculating the union of all keys
    all_keys = set(c1.keys()).union(set(c2.keys()))

    # Converting frequencies to probabilities
    total1 = sum(c1.values())
    total2 = sum(c2.values())
    prob1 = [c1[key] / total1 for key in all_keys]
    prob2 = [c2[key] / total2 for key in all_keys]
    js_distance = jensenshannon(prob1, prob2)

    # The Jensen-Shannon divergence is the square of the distance
    js_divergence = js_distance ** 2
    return js_divergence

def llist_to_list(llist):
    """
    llist is a list of lists. 
    we convert it to a flat list.
    """
    return [item for sublist in llist for item in sublist]


def get_semantic_similarity(s1, s2, num_nn):
    # pip install sentence-transformers sklearn
    # Load the model and compute embeddings
    os.environ['http_proxy'] = HTTP_PROXY
    os.environ['https_proxy'] = HTTPS_PROXY
    # .from_pretrained(self._enc_dec, cache_dir = "/home/cse/btech/cs1200374/tiara_stuff/lib_cache", local_files_only=True)
    # model = SentenceTransformer.from_pretrained('all-MiniLM-L6-v2', cache_dir = "/home/prayushi/Desktop/KB-BINDER_bkp/lib_cache", local_files_only=False)
    model = SentenceTransformer('all-MiniLM-L6-v2')
    # model = SentenceTransformer.from_pretrained('all-MiniLM-L6-v2', )
    del os.environ['http_proxy']
    del os.environ['https_proxy']
    # Generate embeddings
    embeddings_1 = model.encode(s1)
    embeddings_2 = model.encode(s2)

    # Compute pairwise cosine similarities and take the average
    similarities = cosine_similarity(embeddings_1, embeddings_2)
    # avg_similarity = np.mean(similarities)
    # return avg_similarity

    # Initialize a variable to store the sum of average similarities
    total_avg_similarity = 0

    # Iterate over each row in the similarity matrix
    for sim in similarities:
        # Get the 'num_nn' closest embeddings based on cosine similarity
        closest_indices = np.argsort(sim)[-num_nn:]
        closest_similarities = sim[closest_indices]

        # Compute the average similarity for these 'num_nn' closest embeddings
        avg_similarity = np.mean(closest_similarities)
        total_avg_similarity += avg_similarity

    # Compute the overall average of the average similarities
    overall_avg_similarity = total_avg_similarity / len(similarities)

    return overall_avg_similarity
    

def topic_coherence_score(s1, s2):
    # this one is useless...pls leave it
    # pip install gensim nltk
    # nltk.download('punkt')
    # Prepare data
    questions_combined = s1+s2
    tokenized_questions = [word_tokenize(question.lower()) for question in questions_combined]

    # Create a dictionary representation of the documents
    dictionary = Dictionary(tokenized_questions)

    # Filter out words that occur less than 20 documents, or more than 50% of the documents
    dictionary.filter_extremes(no_below=1, no_above=0.5)

    # Create a bag-of-words representation of the documents
    corpus = [dictionary.doc2bow(doc) for doc in tokenized_questions]

    # # Train LDA model
    # lda = LdaModel(corpus, num_topics=2, id2word=dictionary, passes=10)

    # # Compute Topic Coherence Score (this is a simplified example; in practice, use more sophisticated methods)
    # topic_coherence = lda.top_topics(corpus)[0][1]
    num_topics = 5  # Example adjustment; tweak based on your data
    lda = LdaModel(corpus, num_topics=num_topics, id2word=dictionary, passes=10, random_state=100)

    # Compute Coherence Score using CoherenceModel
    coherence_model_lda = CoherenceModel(model=lda, texts=tokenized_questions, dictionary=dictionary, coherence='c_v')
    coherence_lda = coherence_model_lda.get_coherence()

    return coherence_lda
    # return topic_coherence

def keyword_overlap_score(s1, s2):
    # pip install nltk
    # Initialize a TF-IDF Vectorizer
    vectorizer = TfidfVectorizer(stop_words='english')

    # Combine the questions and fit_transform
    tfidf_matrix = vectorizer.fit_transform(s1+s2)

    # Extract feature names
    feature_names = vectorizer.get_feature_names_out()

    # Function to extract top N keywords from a set of questions
    def extract_top_n_keywords(tfidf_matrix, dataset_idx, top_n=4): # 5 earlier
        top_n_keywords = set()
        for idx in dataset_idx:
            row_data = tfidf_matrix[idx].toarray().flatten()
            top_n_indices = row_data.argsort()[-top_n:]
            top_n_keywords.update([feature_names[i] for i in top_n_indices])
        return top_n_keywords

    # Extract top N keywords for each set
    top_keywords_1 = extract_top_n_keywords(tfidf_matrix, range(len(s1)))
    top_keywords_2 = extract_top_n_keywords(tfidf_matrix, range(len(s1), len(s1+s2)))

    # Compute Jaccard similarity
    intersection = top_keywords_1.intersection(top_keywords_2)
    union = top_keywords_1.union(top_keywords_2)
    jaccard_similarity = len(intersection) / len(union)
    return jaccard_similarity

def get_avg_qn_length(s1):
    s1_tot_len = 0
    for qn in s1:
        s1_tot_len += len(qn.split(' '))
    s1_avg_len = s1_tot_len/len(s1)
    return s1_avg_len

def get_semantic_similarity_lf_nl(lf_series, nl_qn_series):
    os.environ['http_proxy'] = HTTP_PROXY
    os.environ['https_proxy'] = HTTPS_PROXY
    model = SentenceTransformer('all-MiniLM-L6-v2')
    del os.environ['http_proxy']
    del os.environ['https_proxy']
    
    similarities = []
    # for lf, nl_qn in zip(lf_series, nl_qn_series):
    #     lf_embedding = model.encode([lf])[0]
    #     nl_qn_embedding = model.encode([nl_qn])[0]
    #     similarity = cosine_similarity([lf_embedding], [nl_qn_embedding])[0][0]
    #     similarities.append(similarity)

    lf_embeddings = model.encode(lf_series)  # lf_series should be a list or iterable of sentences
    nl_qn_embeddings = model.encode(nl_qn_series)  # nl_qn_series should be a list or iterable of sentences

    # Compute cosine similarities in a vectorized manner
    similarities = cosine_similarity(lf_embeddings, nl_qn_embeddings)

    # Since you are computing pair-wise similarity, we assume lf_series and nl_qn_series are of the same length and aligned
    # Extracting diagonal elements will give you the similarity between corresponding elements
    diagonal_similarities = similarities.diagonal()

    # If you need the similarities as a list
    similarities_list = diagonal_similarities.tolist()
    
    avg_similarity = sum(similarities_list) / len(similarities_list)
    return avg_similarity
    
    

if __name__ == '__main__':
    prefix = '/home/prayushi/Desktop/KB-BINDER_bkp/data/'
    suffix = '.json'
    #TODO: correct the graphqa_webqsp datasets
    source_datasets = [ 'grailqa_v1.0_train','graphqa_train_100_final','grailqa_v1.0_train', 'webqsp_train_100shot', 'webqsp_0107.train2',     'grailqa_train_100_final',  'webqsp_0107.train2',               'graphqa_train_100shot_webqsp_graphqa', 'grailqa_v1.0_train',]
    target_datasets = [  'graphqa_test_500',  'graphqa_test_500' ,     'webqsp_0107.test500', 'webqsp_0107.test500','grailqa_test_500_final', 'grailqa_test_500_final',    'graphqa_test_500_webqsp_graphqa',   'graphqa_test_500_webqsp_graphqa'      , 'grailqa_v1.0_dev']
    
    df = pd.DataFrame(columns=['source', 'target', 
                                'num_node_js_div', 'num_node_kl_avg', 'num_node_avg_src', 'num_node_avg_tgt',
                                'num_edges_js_div', 'num_edges_kl_avg', 'num_edges_avg_src', 'num_edges_avg_tgt',
                                'function_js_div', 'function_kl_avg', 'function_perc_new_qns',
                                'rel_js_div', 'rel_kl_avg', 'rel_perc_new_qns', 
                                'type_js_div', 'type_kl_avg', 'type_perc_new_qns', 
                                'dom_js_div', 'dom_kl_avg', 'dom_perc_new_qns',
                                'ent_js_div', 'ent_kl_avg', 'ent_perc_new_qns', # 1. all entities, relns etc in entire dataset
                                'semantic_sim_nn1', 'semantic_sim_nn5', 'keyword_jaccard_sim5',  'avg_nl_src_length', 'avg_nl_tgt_length', # 2. similarity b/w nl qns
                                'skeleton_js_div', 'skeleton_kl_avg', # 3. similarity b/w 2 sets of lf
                                'semantic_sim_lf_nl_T', 'semantic_sim_lf_nl_S' # 4. similarity b/w lf & nl
                               ])
    all_datasets = list(set(source_datasets+target_datasets))
    

    for i in range(len(source_datasets)):
        # add a row to df
        df.loc[i]= [None]*len(df.columns)
        df.at[i, 'source'] = source_datasets[i]
        df.at[i, 'target'] = target_datasets[i]
        dataset1 = json.load(open(prefix+source_datasets[i]+suffix))
        dataset2 = json.load(open(prefix+target_datasets[i]+suffix))

        print('--------------')
        print('Source Dataset: ', source_datasets[i])
        print('Target Dataset: ', target_datasets[i])


        d1_num_node_series = [item['num_node'] for item in dataset1]
        d2_num_node_series = [item['num_node'] for item in dataset2]
        # print('node series')
        # print(d1_num_node_series)
        # print(d2_num_node_series)
        print(get_corr_series(d1_num_node_series, d2_num_node_series))
        df.at[i, 'num_node_js_div'] = get_js_div(d1_num_node_series, d2_num_node_series)
        df.at[i, 'num_node_kl_avg'] = 0.5*(get_kl_div(d1_num_node_series, d2_num_node_series) + get_kl_div(d2_num_node_series, d1_num_node_series))
        df.at[i, 'num_node_avg_src'] = np.mean(d1_num_node_series)
        df.at[i, 'num_node_avg_tgt'] = np.mean(d2_num_node_series)

        d1_num_edge_series = [item['num_edge'] for item in dataset1]
        d2_num_edge_series = [item['num_edge'] for item in dataset2]
        # print('edge series')
        # print(d1_num_edge_series)
        # print(d2_num_edge_series)
        print(get_corr_series(d1_num_edge_series, d2_num_edge_series))
        df.at[i, 'num_edges_js_div'] = get_js_div(d1_num_edge_series, d2_num_edge_series)
        df.at[i, 'num_edges_kl_avg'] = 0.5*(get_kl_div(d1_num_edge_series, d2_num_edge_series) + get_kl_div(d2_num_edge_series, d1_num_edge_series))
        df.at[i, 'num_edges_avg_src'] = np.mean(d1_num_edge_series)
        df.at[i, 'num_edges_avg_tgt'] = np.mean(d2_num_edge_series)
        df.to_csv('dataset_compare2.csv')
        continue
        d1_func_series = [item['function'] for item in dataset1]
        d2_func_series = [item['function'] for item in dataset2]
        d1_func_series = [func if func is not None else 'none' for func in d1_func_series]
        d2_func_series = [func if func is not None else 'none' for func in d2_func_series]
        print('function series')
        print(d1_func_series)
        print(d2_func_series)
        df.at[i, 'function_js_div'] = get_js_div(d1_func_series, d2_func_series)
        df.at[i, 'function_kl_avg'] = 0.5*(get_kl_div(d1_func_series, d2_func_series) + get_kl_div(d2_func_series, d1_func_series))
        df.at[i, 'function_perc_new_qns'] = get_new_perc_qns([[func] for func in d2_func_series], d1_func_series)

        d1_rel_series = llist_to_list([get_rels(item) for item in dataset1]) #list of lists
        d2_rel_series = llist_to_list([get_rels(item) for item in dataset2]) #list of lists
        print('relation series')
        print(d1_rel_series)
        print(d2_rel_series)
        df.at[i, 'rel_js_div'] = get_js_div(d1_rel_series, d2_rel_series)
        df.at[i, 'rel_kl_avg'] = 0.5*(get_kl_div(d2_rel_series, d1_rel_series) + get_kl_div(d1_rel_series, d2_rel_series))
        df.at[i, 'rel_perc_new_qns'] = get_new_perc_qns([get_rels(item) for item in dataset2], d1_rel_series)


        d1_type_series = llist_to_list([get_types(get_rels(item)) for item in dataset1]) #list of lists
        d2_type_series = llist_to_list([get_types(get_rels(item)) for item in dataset2]) #list of lists

        print('type series')
        print(d1_type_series)
        print(d2_type_series)
        df.at[i, 'type_js_div'] = get_js_div(d1_type_series, d2_type_series)
        df.at[i, 'type_kl_avg'] = 0.5*(get_kl_div(d1_type_series, d2_type_series) + get_kl_div(d2_type_series, d1_type_series))
        df.at[i, 'type_perc_new_qns'] = get_new_perc_qns([get_types(get_rels(item)) for item in dataset2], d1_type_series)


        d1_dom_series = llist_to_list([get_domains(item) for item in dataset1]) #list of lists
        d2_dom_series = llist_to_list([get_domains(item) for item in dataset2]) #list of lists
        print('domain series')
        print(d1_dom_series)
        print(d2_dom_series)
        df.at[i, 'dom_js_div'] = get_js_div(d1_dom_series, d2_dom_series)
        df.at[i, 'dom_kl_avg'] = 0.5*(get_kl_div(d1_dom_series, d2_dom_series) + get_kl_div(d2_dom_series, d1_dom_series))
        df.at[i, 'dom_perc_new_qns'] = get_new_perc_qns([get_domains(item) for item in dataset2], d1_dom_series)

        d1_ent_series = llist_to_list([get_entities(item) for item in dataset1]) #list of lists
        d2_ent_series = llist_to_list([get_entities(item) for item in dataset2]) #list of lists
        print('entity series')
        print(d1_ent_series)
        print(d2_ent_series)
        print('KL divergence (target, source) entities:',  get_kl_div(d2_ent_series, d1_ent_series))
        print('KL divergence (source, target) entities: ', get_kl_div(d1_ent_series, d2_ent_series))
        print('JS divergence: ', get_js_div(d1_ent_series, d2_ent_series))
        print('### percentage of questions in the target having unseen entities: ', get_new_perc_qns([get_entities(item) for item in dataset1], d2_rel_series))
        df.at[i, 'ent_js_div'] = get_js_div(d1_ent_series, d2_ent_series)
        df.at[i, 'ent_kl_avg'] = 0.5*(get_kl_div(d2_ent_series, d1_ent_series) + get_kl_div(d1_ent_series, d2_ent_series))
        df.at[i, 'ent_perc_new_qns'] = get_new_perc_qns([get_entities(item) for item in dataset2], d1_ent_series)

        d1_nl_qns = [item['question'] for item in dataset1]
        d2_nl_qns = [item['question'] for item in dataset2]
        df.at[i, 'semantic_sim_nn1'] = get_semantic_similarity(d1_nl_qns, d2_nl_qns, 1)
        df.at[i, 'semantic_sim_nn5'] = get_semantic_similarity(d1_nl_qns, d2_nl_qns, 5)
        df.at[i, 'keyword_jaccard_sim5'] = keyword_overlap_score(d1_nl_qns, d2_nl_qns)
        df.at[i, 'avg_nl_src_length'] = get_avg_qn_length(d1_nl_qns)
        df.at[i, 'avg_nl_tgt_length'] = get_avg_qn_length(d2_nl_qns)





        d1_lf_skeletons_series = [get_skeleton(item['s_expression'], source_datasets[i]) for item in dataset1]
        d2_lf_skeletons_series = [get_skeleton(item['s_expression'], target_datasets[i]) for item in dataset2]
        print('lf_skeleton_series')
        print(d1_lf_skeletons_series)
        print(d2_lf_skeletons_series)
        df.at[i, 'skeleton_js_div'] = get_js_div(d1_lf_skeletons_series, d2_lf_skeletons_series)
        df.at[i, 'skeleton_kl_avg'] = 0.5*(get_kl_div(d2_lf_skeletons_series, d1_lf_skeletons_series) + get_kl_div(d1_lf_skeletons_series, d2_lf_skeletons_series))



        d1_lf = [item['s_expression'] for item in dataset1]
        d2_lf = [item['s_expression'] for item in dataset2]

        d1_lf = [s_expr if s_expr is not None else '' for s_expr in d1_lf]
        d2_lf = [s_expr if s_expr is not None else '' for s_expr in d2_lf]

        ss1 =  get_semantic_similarity_lf_nl(d1_lf, d1_nl_qns)
        ss2 = get_semantic_similarity_lf_nl(d2_lf, d2_nl_qns)
        df.at[i, 'semantic_sim_lf_nl_T'] = ss2
        df.at[i, 'semantic_sim_lf_nl_S'] = ss1

        df.to_csv('dataset_compare.csv')

# FUn : Model-agnostic Logical-form Refinement for KBQA with Unanswerability

[[video](https://drive.google.com/file/d/1Zbu6Ec14XHoZJxMjVFI982VyPNeqMLUP/view?usp=sharing)] | 
[[slides](https://docs.google.com/presentation/d/1vmsktNXRjnVcq5Xm4jM7L4JfhNj7EBQY/edit?usp=drive_link&ouid=115447969639729561298&rtpof=true&sd=true)] | 
[[poster](https://drive.google.com/file/d/1CY_YRxk0R38Cxmxi9Q8rgQRcijIgKeUL/view?usp=sharing)]

## Architecture
![alt text](https://github.com/dair-iitd/FUn-FuSIC/blob/main/FUn-FuSIC%20Architeture.jpg)

## To run the code 
```
python3 main.py config.json 
```
## Pre-Trained Checkpoints
We have uploaded checkpoints for both fintuned Pangu and RetinaQA baselines [[Checkpoints](https://www.kaggle.com/models/samratya213/fun-fusic/)]

## Error correction using feedback mechanisms
In this section, we enlist the different types of generation errors that we observe the LLM to make, and we provide the LLM feedback based on the error.
### Strong Verifier Checks 
These verifiers, if failed, assure that the logical form is incorrect 
1. **Syntax Error**: The query is not executable on the KG server because it is badly formed. It can be determined by solely checking the sparql query. 
   - `syntax`: The query doesn't execute on the server and returns an error message. We provide the error message obtained as feedback to the LLM. 
2. **KB Inconsistency Errors**: This category of errors corresponds to logical forms that although execute without error on the KB, but they return an empty/incorrect answer because the query isn't meaningful with respect to the underlying query. It can be determined by checking  the sparql query along with the KB ontology and entity types. 
   - `grounding`: The query contains a class/relation/entity that wasn't provided as a part of the KB context. We provide the specific class/relation/entity that isn't defined for the KB as feedback to the LLM. 
   - `lf_semantic`: There exists a variable/entity in the sparql query for which the classes assigned by type or relation constraints are mutually incompatible(i.e. there exists no element in the KB which simultaneously belongs to all the classes that have been assigned to that variable) . We provide the variable/entity for which the classes don't match, the types assigned to it along with the relations that assign those types as feedback to the LLM.
   - `float_suffix`: Some KBs(including freebase) perform numeric computations(>, <, >=, <=, =) incorrectly if the constant values aren't correctly typecasted as being float. We provide the correct typecasting syntax as feedback to the LLM.
### Weak Verifier Checks 
These verifiers, if failed, mean that the logical form has a high probability of being incorrect (though not guaranteed to be incorrect) 
1. **Question Logical Form Disagreement Error**: The natural language question that we're answering isn't same as the natural language question originally asked. It can be determined based on the query, the natural language question asked and the KB context. (2 questions might be similar/dissimilar based on the KB context)
    - `nl_semantic`: The logical form predicted isn't equivalent to the original natural language question conditioned on the KB context. We provide the original natural language question, the natural language version of the query we answer as feedback to the LLM. 
2. **Answer Inconsistency**: Upon executing the query over the KB, we notice something about the answer, that makes us believe that the answer is definetely incorrect. It can be determined by checking the predicted query and the predicted answer only. 
   - `qans`: The query upon exection returns as answer the topic entity of the question (i.e. the answer "ans" is same as the topic entity question node "q"). We provide feedback that upon execution the answer is same as the topic entity node mentioned in the question. 
   - `intermediate`: The query upon execution returns as answer a "compound value type" node (the node doesn't correspond to a real-world entity, and is rather an intermediate node used to compactly store n-ary relations using binary edges by davidsonian semantics)
   - `egf`: The query upon execution returns an empty answer. We provide feedback that upon execution the query returns an empty answer. 



## Implementation of checkers
All the above stated feedbacks will be possible only if we're able to identify such errors in the logical form correctly. 
Note that other than `nl_semantic`, all other types of errors can be detected using symbolic checkers, and hence can be identified with perfect accuracy. Furthermore, the logical form is guaranteed to return an incorrect answer if any of these errors exist. Therefore, feedback provided based on these errors can only improve the performance further. 

However, implementing the `nl_semantic` check can be more tricky. We need to implement a machine learning model for this task, as a straightforward symbolic check isn't possible. The overall performance of the KBQA model will depend upon the performance of this subtask. Specifically, providing incorrect feedback (i.e. raising an `nl_semantic` error where it doesn't exist) might lead to an incorrect final answer(post LLM-feedback) despite a correct initial answer. 

We follow a two-step approach for this task. 
1. **Back-translation**: Conversion of the sparql query into a corresponding natural language question (we will further refer this to be the predicted natural language question). 
2. **Natural Language Semantic Discrimination**: Given a pair of natural language questions, predict whether they have the same meaning or not. 

With the advancement of LLMs, step-1 is easy to achieve and can be done directly via zero-shot prompting to an LLM. 

For step-2, we use **LLM prompting**: Provide 6 in-context examples (3 positive + 3 negative, all come from the validation dataset) along with an LLM-based explanation of why they have same or different meanings. Essentially, Few shot + Chain-of-Thought prompting. 

## Self consistency for Unanswerability 
We use a modified version of self consistency, wherein we only select the most popular answer only if it accounts for atleast half of all possible answers. This is to account for cases where a single answer might have enough support via different reasoning paths, however, no logical form by itself satisfies the question-logical form disagreement verifier. Here, we select the popular answer(as the question-logical form disagreement verifier might be possibly incorrect) 



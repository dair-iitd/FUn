# python main.py config.json 'ablation_graphqa/graphqa_50U_1.json' &
# python main.py config.json 'ablation_graphqa/graphqa_50U_2.json' &

# python main.py config.json 'ablation_graphqa/graphqa_U_data_level_15.json' &
# python main_new.py config.json 'pangu/graphqa_50A_50U_restructured.json' &
# python main_new.py config.json 'pangu/grailqa_test_ablation_subset_50A_50U.json' &
# /home/scai/phd/aiz248314/KBQA/FuSIC-KBQA-EGF/fusic-kbqa-egf/

# python main.py config.json 'ablations_grailqa/result_wo_cvt_feedback/rem/grailqa_test_ablation_subset_50U_4.json' &
# python main.py config.json 'ablation_graphqa/graphqa_50A_2.json' &
# python main.py config.json 'ablation_graphqa/graphqa_50U_1.json' &
# python main.py config.json 'ablation_graphqa/graphqa_50U_2.json' &

# python main.py config.json 'ablations_grailqa/grailqa_test_ablation_subset_50A_1.json' &
# python main.py config.json 'ablations_grailqa/grailqa_test_ablation_subset_50A_2.json' &


# python main.py config.json 'ablations_grailqa/grailqa_test_ablation_subset_50U_1.json' &
# python main.py config.json 'ablations_grailqa/grailqa_test_ablation_subset_50U_2.json' &

python main_answerable.py FUn/answerable_grail_5pc/config_grailqa_pangu.json &
python main_answerable.py FUn/answerable_grail_5pc/config_grailqa_retinaqa.json &

python main_answerable.py FUn/answerable_grail_10pc/config_grailqa_pangu.json &
python main_answerable.py FUn/answerable_grail_10pc/config_grailqa_retinaqa.json &
import argparse
import nltk
import os
import scipy.sparse

from nltk.corpus import stopwords
from nltk.stem.snowball import SnowballStemmer
from nltk.tokenize import RegexpTokenizer
from utils import *

nltk.download('stopwords')


def main():

    # Setting NLP pre-processing features
    stop_words = set(stopwords.words('english'))
    tokenizer = RegexpTokenizer(r'\w+')
    stemmer = SnowballStemmer(language='english')

    # Make directory for storing intermediate matrices/model
    path_matrices = args.path_write_data + 'matrices'
    path_model = args.path_write_data + 'models'

    if not os.path.isdir(path_matrices):
        os.mkdir(path_matrices)
    del path_matrices

    if not os.path.isdir(path_model):
        os.mkdir(path_model)
    del path_model

    # Get the relevant informations on the dataset
    print('Get the relevant channels...')
    set_relevant_channels = get_relevant_channels(args.n_min_sub)

    print('Get the vocabulary (first pass)...')
    set_stemmed_tokens, set_relevant_vid = get_vocab(
        args.path_dataset, set_relevant_channels, args.n_min_views, args.use_bigram, stop_words, tokenizer, stemmer)

    # Get the dictionnary
    word2id, id2word = get_word2id(set_stemmed_tokens)

    # Construct the doc-term sparse matrix
    print('Get the document-term matrix...')
    S = get_document_term_matrix(
        args.path_dataset, args.path_write_data, set_relevant_vid, word2id, args.use_bigram, stop_words, tokenizer, stemmer)

    # Get index of the selected vidos for topic modelling
    print('Find indexes of relevant videos for topic modelling...')
    set_relevant_vid_final = get_vid_for_tm(set_relevant_vid, n_top=args.n_top_vid_per_combination)

    #  Get the doc-term matrix fot topic modelling with the corresponding dictionnary of tokens
    print('Get the final document-term matrix for topic modelling...')
    S_final, id2word_final = get_document_term_matrix_for_tm(S, set_relevant_vid_final, id2word, args.min_vid_per_token)

    spark, conf = create_spark_session(
        args.n_jobs, args.executor_mem, args.driver_mem)

    print('Generate the data for topic modelling with pyspark...')
    data_for_tm = get_data_for_tm(S_final, spark)

    # Save results
    print('Save all the results...')
    save_to_pickle(set_relevant_channels,'set_relevant_channels', args.path_write_data)
    save_to_pickle(set_stemmed_tokens, 'set_stemmed_tokens', args.path_write_data)
    save_to_pickle(set_relevant_vid, 'set_relevant_vid', args.path_write_data)
    save_to_pickle(set_relevant_vid_final, 'set_relevant_vid_final', args.path_write_data)
    save_to_pickle(id2word, 'id2word', args.path_write_data)
    save_to_pickle(id2word_final, 'id2word_final', args.path_write_data)

    scipy.sparse.save_npz(args.path_write_data + 'matrices/S_full.npz', S)
    scipy.sparse.save_npz(args.path_write_data + 'matrices/S_final.npz', S_final)

    if os.path.isdir(args.path_write_data + 'models/sparkdf.json'):
        print('The file data for topic modelling already exists.')
    else:
        data_for_tm.write.option('compression', 'gzip').json(args.path_write_data + 'models/sparkdf.json')

    print('Task Done!')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    # Arguments related to data
    parser.add_argument('--path_dataset', dest='path_dataset',
                        default='/dlabdata1/youtube_large/yt_metadata_en.jsonl.gz',
                        help='path of the dataset')
    parser.add_argument('--path_write_data', dest='path_write_data',
                        default='/dlabdata1/youtube_large/olam/data/test/',
                        help='path to folder where we keep intermediate results')

    # Arguments related to the pre-processing of the data for topic modelling
    parser.add_argument('--n_min_sub', dest='n_min_sub', type=int, default=100000,
                        help='Threshold for the minimum number of subscrbers for relevant channels')
    parser.add_argument('--n_min_views', dest='n_min_views', type=int, default=10000,
                        help='Threshold for the minimum number of views for relevant videos')
    parser.add_argument('--use_bigram', dest='use_bigram', default=False,
                        action='store_true', help='If True, generate bi-grams for the vocabulary')
    parser.add_argument('--min_vid_per_token', dest='min_vid_per_token', type=int, default=100,
                        help='Threshold for tokens that appear in at least min_vid_per_token videos to be considered '
                             'as relevant tokens')
    parser.add_argument('--n_top_vid_per_combination', dest='n_top_vid_per_combination', type=int, default=20,
                        help='Threshold for selecting the number videos with the most views for each combination of '
                             '\'category\', \'uploaded_year\' and \'channel_id\' for topic modelling')

    #  Arguments related to Pyspark for generating data for topic modelling
    parser.add_argument('--n_jobs', dest='n_jobs', type=int, default=4,
                        help='The number of jobs for creating the data for topic modelling')
    parser.add_argument('--executor_mem', dest='executor_mem',
                        type=int, default=8, help='The memory in g for each executor')
    parser.add_argument('--driver_mem', dest='driver_mem',
                        type=int, default=64, help='The memory in g for the driver')

    args = parser.parse_args()

    main()

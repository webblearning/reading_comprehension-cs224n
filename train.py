from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import json

import tensorflow as tf

from qa_model import Encoder, QASystem, Decoder
from os.path import join as pjoin
import numpy as np

from utils.read_data import mask_dataset
from utils.read_data import read_answers, read_raw_answers
from Config import Config as cfg

import logging

logging.basicConfig(level=logging.INFO)

tf.app.flags.DEFINE_float("learning_rate", 0.01, "Learning rate.")
tf.app.flags.DEFINE_float("max_gradient_norm", 10.0, "Clip gradients to this norm.")
tf.app.flags.DEFINE_float("dropout", 0.15, "Fraction of units randomly dropped on non-recurrent connections.")
tf.app.flags.DEFINE_integer("batch_size", 10, "Batch size to use during training.")
tf.app.flags.DEFINE_integer("epochs", 10, "Number of epochs to train.")
tf.app.flags.DEFINE_integer("state_size", 200, "Size of each model layer.")
tf.app.flags.DEFINE_integer("output_size", 750, "The output size of your model.")
tf.app.flags.DEFINE_integer("embedding_size", 100, "Size of the pretrained vocabulary.")
tf.app.flags.DEFINE_string("data_dir", "data/squad", "SQuAD directory (default ./data/squad)")
tf.app.flags.DEFINE_string("train_dir", "train_drop", "Training directory to save the model parameters (default: ./train).")
tf.app.flags.DEFINE_string("load_train_dir", "", "Training directory to load model parameters from to resume training (default: {train_dir}).")
tf.app.flags.DEFINE_string("log_dir", "log", "Path to store log and flag files (default: ./log)")
tf.app.flags.DEFINE_string("optimizer", "adam", "adam / sgd")
tf.app.flags.DEFINE_integer("print_every", 1, "How many iterations to do per print.")
tf.app.flags.DEFINE_integer("keep", 0, "How many checkpoints to keep, 0 indicates keep all.")
tf.app.flags.DEFINE_string("vocab_path", "data/squad/vocab.dat", "Path to vocab file (default: ./data/squad/vocab.dat)")
tf.app.flags.DEFINE_string("embed_path", "", "Path to the trimmed GLoVe embedding (default: ./data/squad/glove.trimmed.{embedding_size}.npz)")

FLAGS = tf.app.flags.FLAGS


def initialize_model(session, model, train_dir):
    ckpt = tf.train.get_checkpoint_state(train_dir)
    v2_path = ckpt.model_checkpoint_path + ".index" if ckpt else ""
    if ckpt and (tf.gfile.Exists(ckpt.model_checkpoint_path) or tf.gfile.Exists(v2_path)):
        logging.info("Reading model parameters from %s" % ckpt.model_checkpoint_path)
        model.saver.restore(session, ckpt.model_checkpoint_path)
    else:
        logging.info("Created model with fresh parameters.")
        session.run(tf.global_variables_initializer())
        logging.info('Num params: %d' % sum(v.get_shape().num_elements() for v in tf.trainable_variables()))
    return model


def initialize_vocab(vocab_path):
    if tf.gfile.Exists(vocab_path):
        rev_vocab = []
        with tf.gfile.GFile(vocab_path, mode="rb") as f:
            rev_vocab.extend(f.readlines())
        rev_vocab = [line.strip('\n') for line in rev_vocab]
        # (word, index)
        vocab = dict([(x, y) for (y, x) in enumerate(rev_vocab)])
        return vocab, rev_vocab
    else:
        raise ValueError("Vocabulary file %s not found.", vocab_path)


def get_normalized_train_dir(train_dir):
    """
    Adds symlink to {train_dir} from /tmp/cs224n-squad-train to canonicalize the
    file paths saved in the checkpoint. This allows the model to be reloaded even
    if the location of the checkpoint files has moved, allowing usage with CodaLab.
    This must be done on both train.py and qa_answer.py in order to work.
    """
    global_train_dir = '/tmp/cs224n-squad-train'
    if os.path.exists(global_train_dir):
        os.unlink(global_train_dir)
    if not os.path.exists(train_dir):
        os.makedirs(train_dir)
    os.symlink(os.path.abspath(train_dir), global_train_dir)
    return global_train_dir


def main(_):

    data_dir = cfg.DATA_DIR
    # Do what you need to load datasets from FLAGS.data_dir
    set_names = ['train', 'val']
    suffixes = ['context', 'question']
    dataset = mask_dataset(data_dir, set_names, suffixes)
    '''
    dataset is a dict with
    {'train-context': [(data, mask),...],
     'train-question': [(data, mask),...],
     'val-context': [(data, mask),...],
     'val-question': [(data,mask),...]}
    '''
    answers = read_answers(data_dir)
    raw_answers = read_raw_answers(data_dir)

    embed_path = FLAGS.embed_path or pjoin("data", "squad", "glove.trimmed.{}.npz".format(FLAGS.embedding_size))
    # vocab_path = FLAGS.vocab_path or pjoin(data_dir, "vocab.dat")
    vocab_path = pjoin(data_dir, "vocab.dat")
    vocab, rev_vocab = initialize_vocab(vocab_path)

    # encoder = Encoder(size=FLAGS.state_size, vocab_dim=FLAGS.embedding_size)
    # decoder = Decoder(output_size=FLAGS.output_size)

    import time
    c_time = time.strftime('%Y%m%d_%H%M',time.localtime())
    if not os.path.exists(FLAGS.log_dir):
        os.makedirs(FLAGS.log_dir)
    file_handler = logging.FileHandler(pjoin(FLAGS.log_dir, 'log'+c_time+'.txt'))
    logging.getLogger().addHandler(file_handler)

    print(vars(FLAGS))
    with open(os.path.join(FLAGS.log_dir, "flags.json"), 'w') as fout:
        json.dump(FLAGS.__flags, fout)
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    ##########

    #############


    default = True
    model_pathes = 'train/'
    starts = np.zeros((4000, 4),dtype=np.int32)
    ends = np.zeros((4000,4),dtype=np.int32)
    for i in xrange(4):
        mp = model_pathes + str(i+1)
        tf.reset_default_graph()
        if default:
            lr = 1e-3
            default = False
        else:
            lr = 10**np.random.uniform(-7, 1)
        print('=========== lr={} ==========='.format(lr))
        encoder = Encoder()
        decoder = Decoder()

        with tf.Session(config=config) as sess:
            qa = QASystem(sess,encoder, decoder)
            ############
            from tests.eval_test import ensamble
            s, e = ensamble()
            qa.evaluate_answer(sess, dataset, raw_answers, rev_vocab,
                 log=True,
                 # training=False,
                 sendin = (s, e),
                 sam=4000)
            break
            #############
            init = tf.global_variables_initializer()
            sess.run(init)
            # load_train_dir = get_normalized_train_dir(FLAGS.load_train_dir or FLAGS.train_dir)
            load_train_dir = get_normalized_train_dir(mp)
            # for i in tf.trainable_variables():
            #     logging.info(i.name)
            # for i in tf.get_collection(tf.GraphKeys.REGULARIZATION_LOSSES):
            #     print(i.name)
            initialize_model(sess, qa, load_train_dir)

            save_train_dir = get_normalized_train_dir(FLAGS.train_dir)
            # saver = tf.train.Saver()
            # qa.train(sess, dataset,answers,save_train_dir,  debug_num=100)
            # qa.train(lr, sess,dataset,answers,save_train_dir, raw_answers=raw_answers,
                     # debug_num=100,
                     # rev_vocab=rev_vocab)
            #
            temp_answer = qa.evaluate_answer(sess, dataset, raw_answers, rev_vocab,
                 log=True,
                 # training=False
                 sam=4000)
            starts[:, i] = temp_answer[0]
            ends[:, i] = temp_answer[1]

    # np.save('train/cache.npy',(starts, ends))
    # s = np.mean(starts, axis=1, dtype=np.int32)
    # e = np.mean(ends, axis=1, dtype=np.int32)
    # qa.evaluate_answer(sess, dataset, raw_answers, rev_vocab,
    #              log=True,
    #              # training=False,
    #              sendin = (s, e),
    #              sam=4000)

if __name__ == "__main__":
    tf.app.run()
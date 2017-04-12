# -*- coding: utf-8 -*-
import nltk, json, pickle, sys, itertools,collections, jieba, os
from random import shuffle
from nltk.collocations import BigramCollocationFinder
from nltk.metrics import BigramAssocMeasures
from nltk.probability import FreqDist, ConditionalFreqDist
from nltk.classify.scikitlearn import SklearnClassifier
from sklearn.svm import SVC, LinearSVC, NuSVC
from sklearn.naive_bayes import MultinomialNB, BernoulliNB
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from nltk.metrics.scores import (accuracy, precision, recall, f_measure, log_likelihood, approxrand)


class Swinger(object):
    """docstring for Swinger"""
    BASEDIR = os.path.dirname(__file__)
    stopwords = json.load(open(os.path.join(BASEDIR, 'stopwords.json'), 'r'))
    classifier_table = {
        'SVC':SVC(probability=False),
        'LinearSVC':LinearSVC(),
        'NuSVC':NuSVC(probability=False),
        'MultinomialNB':MultinomialNB(),
        'BernoulliNB':BernoulliNB()
    }
    
    def __init__(self):
        self.train = []
        self.test = []
        self.classifier = ''

    def load(self, model, useDefault=True, pos=None, neg=None, BestFeatureVec=2000):
        BestFeatureVec = int(BestFeatureVec)

        if useDefault:
            print('load default bestMainFeatures')
            self.bestMainFeatures = pickle.load(open(os.path.join(self.BASEDIR, 'bestMainFeatures.pickle.{}'.format(BestFeatureVec)), 'rb'))
            print('load default bestMainFeatures success!!')

            self.classifier = pickle.load(open(os.path.join(self.BASEDIR, '{}.pickle.{}'.format(model, BestFeatureVec)), 'rb'))
            print("load model from {}".format(model))
        else:
            try:
                print('load local bestMainFeatures')
                self.bestMainFeatures = pickle.load(open('bestMainFeatures.pickle.{}'.format(BestFeatureVec), 'rb'))
                print('load local bestMainFeatures success!!')

                self.classifier = pickle.load(open('{}.pickle.{}'.format(model, BestFeatureVec), 'rb'))
                print("load model from {}".format(model))
            except Exception as e:
                # build best features.
                print('load bestMainFeatures failed!!\nstart creating bestMainFeatures ...')

                self.pos_origin = json.load(open(pos, 'r'))
                self.neg_origin = json.load(open(neg, 'r'))
                shuffle(self.pos_origin)
                shuffle(self.neg_origin)
                poslen = len(self.pos_origin)
                neglen = len(self.neg_origin)

                # build train and test data.
                self.pos_review = self.pos_origin[:int(poslen*0.9)]
                self.pos_test = self.pos_origin[int(poslen*0.9):]
                self.neg_review = self.neg_origin[:int(neglen*0.9)]
                self.neg_test = self.neg_origin[int(neglen*0.9):]

                MainPosFeatures, MainNegFeatures = self.create_Mainfeatures(bigram=True, pos_data=self.pos_review, neg_data=self.neg_review) #ʹ�ôʺ�˫�ʴ�����Ϊ����
                def find_best_words(number):
                    MainPosFeatures.update(MainNegFeatures)
                    best = sorted(MainPosFeatures.items(), key=lambda x: -x[1])[:number] #�Ѵʰ���Ϣ����������number��������ά�ȣ��ǿ��Բ��ϵ���ֱ�����ŵ�
                    return set(w for w, s in best)

                self.bestMainFeatures = find_best_words(BestFeatureVec) #����ά��1500
                pickle.dump(self.bestMainFeatures, open('bestMainFeatures.pickle.{}'.format(BestFeatureVec), 'wb'))


                # build model
                print('start building {} model!!!'.format(model))

                self.classifier = SklearnClassifier(self.classifier_table[model]) #��nltk ��ʹ��scikit-learn �Ľӿ�
                if len(self.train) == 0:
                    print('build training data')
                    posFeatures = self.emotion_features(self.best_Mainfeatures, self.pos_review, 'pos')
                    negFeatures = self.emotion_features(self.best_Mainfeatures, self.neg_review, 'neg')
                    self.train = posFeatures + negFeatures
                self.classifier.train(self.train) #ѵ��������
                pickle.dump(self.classifier, open('{}.pickle.{}'.format(model, BestFeatureVec),'wb'))

    def buildTestData(self, pos_test, neg_test):
        pos_test = json.load(open(pos_test, 'r'))
        neg_test = json.load(open(neg_test, 'r'))
        posFeatures = self.emotion_features(self.best_Mainfeatures, pos_test, 'pos')
        negFeatures = self.emotion_features(self.best_Mainfeatures, neg_test, 'neg')
        return posFeatures + negFeatures

    def best_Mainfeatures(self, word_list):
        return {word:True for word in word_list if word in self.bestMainFeatures}

    @staticmethod
    def create_Mainfeatures(bigram, pos_data, neg_data):
        posWords = list(itertools.chain(*pos_data)) #�Ѷ�ά���������һά����
        negWords = list(itertools.chain(*neg_data)) #ͬ��

        if bigram == True:
                bigram_finder = BigramCollocationFinder.from_words(posWords)
                posBigrams = bigram_finder.nbest(BigramAssocMeasures.chi_sq, 5000)
                bigram_finder = BigramCollocationFinder.from_words(negWords)
                negBigrams = bigram_finder.nbest(BigramAssocMeasures.chi_sq, 5000)
                posWords += posBigrams #�ʺ�˫�ʴ���
                negWords += negBigrams

        word_fd = FreqDist() #��ͳ�����дʵĴ�Ƶ
        cond_word_fd = ConditionalFreqDist() #��ͳ�ƻ����ı��еĴ�Ƶ�������ı��еĴ�Ƶ
        for word in posWords:
            word_fd[word] += 1
            cond_word_fd['pos'][word] += 1
        for word in negWords:
            word_fd[word] += 1
            cond_word_fd['neg'][word] += 1

        pos_word_count = cond_word_fd['pos'].N() #�����ʵ�����
        neg_word_count = cond_word_fd['neg'].N() #�����ʵ�����
        total_word_count = pos_word_count + neg_word_count

        posFeatures = {}
        negFeatures = {}
        for word, freq in word_fd.items():
            if cond_word_fd['pos'][word] > freq/2:
                posFeatures[word] = BigramAssocMeasures.chi_sq(cond_word_fd['pos'][word], (freq, pos_word_count), total_word_count) #��������ʵĿ���ͳ����������Ҳ���Լ��㻥��Ϣ������ͳ����
            elif cond_word_fd['neg'][word] > freq/2:
                negFeatures[word] = BigramAssocMeasures.chi_sq(cond_word_fd['neg'][word], (freq, neg_word_count), total_word_count) #ͬ��

        return posFeatures, negFeatures # �������ؓ����w��features�֔����_���

    def score(self, pos_test, neg_test):
        # build test data set
        if len(self.test) == 0:
            # self.test = self.buildTestData(self.pos_test, self.neg_test)
            self.test = self.buildTestData(pos_test, neg_test)

        refsets = collections.defaultdict(set)
        testsets = collections.defaultdict(set)
        for i, (feats, label) in enumerate(self.test):
            refsets[label].add(i)
            observed = self.classifier.classify(feats)
            testsets[observed].add(i)

        # pred = classifier.classify_many(self.test) #�Կ������Լ������ݽ��з��࣬����Ԥ��ı�ǩ
        # print(accuracy_score(self.tag_test, pred)) #�Աȷ���Ԥ�������˹���ע����ȷ���������������׼ȷ��
        pprecision = precision(refsets['pos'], testsets['pos']) if precision(refsets['pos'], testsets['pos'])!=None else 0
        print('pos precision:', pprecision)
        print('pos recall:', recall(refsets['pos'], testsets['pos']))
        pfmeasure = f_measure(refsets['pos'], testsets['pos']) if f_measure(refsets['pos'], testsets['pos'])!=None else 0
        print('pos F-measure:', pfmeasure)

        nprecision = 0 if precision(refsets['neg'], testsets['neg'])==None else precision(refsets['neg'], testsets['neg'])
        print('neg precision:', nprecision)
        print('neg recall:',recall(refsets['neg'], testsets['neg']))
        nfmeasure = f_measure(refsets['neg'], testsets['neg']) if f_measure(refsets['neg'], testsets['neg'])!=None else 0
        print('neg F-measure:', nfmeasure)
        print('G-measure:', 2*(nfmeasure*pfmeasure/(nfmeasure+pfmeasure)))
        return 2*(nfmeasure*pfmeasure/(nfmeasure+pfmeasure))

    def emotion_features(self, feature_extraction_method, data, emo):
        return list(map(lambda x:[feature_extraction_method(x), emo], data)) #Ϊ�����ı�����"pos"

    def swing(self, word_list):
        word_list = filter(lambda x: x not in self.stopwords, jieba.cut(word_list))
        sentence = self.best_Mainfeatures(word_list)
        return self.classifier.classify(sentence)

if __name__ == '__main__':
    # import matplotlib.pyplot as plt #���ӻ�ģ��
    NuSVC_arr=[]
    SVC_arr=[]
    LinearSVC_arr=[]
    MultinomialNB_arr=[]
    BernoulliNB_arr=[]
    for i in range(1,5000, 50):
        s = Swinger()
        s.load('NuSVC', useDefault=False, pos=sys.argv[1], neg=sys.argv[2], BestFeatureVec=i)
        NuSVC_arr.append(s.score(pos_test=sys.argv[3], neg_test=sys.argv[4]))

        s.load('SVC', useDefault=False, pos=sys.argv[1], neg=sys.argv[2], BestFeatureVec=i)
        SVC_arr.append(s.score(pos_test=sys.argv[3], neg_test=sys.argv[4]))

        s.load('LinearSVC', useDefault=False, pos=sys.argv[1], neg=sys.argv[2], BestFeatureVec=i)
        LinearSVC_arr.append(s.score(pos_test=sys.argv[3], neg_test=sys.argv[4]))

        s.load('MultinomialNB', useDefault=False, pos=sys.argv[1], neg=sys.argv[2], BestFeatureVec=i)
        MultinomialNB_arr.append(s.score(pos_test=sys.argv[3], neg_test=sys.argv[4]))

        s.load('BernoulliNB', useDefault=False, pos=sys.argv[1], neg=sys.argv[2], BestFeatureVec=i)
        BernoulliNB_arr.append(s.score(pos_test=sys.argv[3], neg_test=sys.argv[4]))

    print(NuSVC_arr)
    print(SVC_arr)
    print(LinearSVC_arr)
    print(MultinomialNB_arr)
    print(BernoulliNB_arr)

    # plt.plot(range(1,5000, 50), NuSVC_arr, 'o-', color="b",label="NuSVC")
    # plt.plot(range(1,5000, 50), SVC_arr, 'o-', color="g",label="SVC")
    # plt.plot(range(1,5000, 50), LinearSVC_arr, 'o-', color="r",label="LinearSVC")
    # plt.plot(range(1,5000, 50), MultinomialNB_arr, 'o-', color="c",label="MultinomialNB")
    # plt.plot(range(1,5000, 50), BernoulliNB_arr, 'o-', color="m",label="BernoulliNB")
    # plt.legend(loc='best')
    # plt.savefig(sys.argv[5]+'.png')
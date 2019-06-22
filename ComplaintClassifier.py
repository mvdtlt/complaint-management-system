# работа с csv-файлом
import csv
# стоп-слова
#import nltk
from nltk.corpus import stopwords
#nltk.download("stopwords")
# предобработка и создание матрицы
from sklearn.feature_extraction.text import TfidfVectorizer
from pymystem3 import Mystem
# метод опорных векторов
from sklearn.svm import LinearSVC
# сохранение состояния обученного классификатора
from joblib import dump, load
import os.path

class ComplaintClassifier:
    def __init__(self):
        self.trained = False
        self.X = []
        self.Y = []
        self.lemmatizer = Mystem()
        self.vectorizer = TfidfVectorizer(min_df=5, max_df=0.5, stop_words=stopwords.words('russian'))
        self.load_train_set()
        if os.path.exists('./clf.joblib'):
            self.classifier = load('./clf.joblib')
            self.trained = True
        else:
            self.classifier = LinearSVC(random_state=0)
            self.trained = False
            self.train()

    def load_train_set(self):
        if os.path.exists('./vect.joblib'):
            self.vectorizer = load('./vect.joblib')
        else:
            f = open('./tlt10.csv')
            reader = csv.DictReader(f, delimiter=',')
            for line in reader:
                lemmatized = ''.join(self.lemmatizer.lemmatize(line["текст"]))
                self.Y.append(line["тематика"])
                self.X.append(lemmatized)
            self.X = self.vectorizer.fit_transform(self.X).toarray()
            dump(self.vectorizer, './vect.joblib')

    def train(self):
        self.classifier.fit(self.X, self.Y)
        self.trained = True
        dump(self.classifier, './clf.joblib')
    
    def predict(self, text):
        text = ''.join(self.lemmatizer.lemmatize(text))
        text = [text]
        return self.classifier.predict(self.vectorizer.transform(text))

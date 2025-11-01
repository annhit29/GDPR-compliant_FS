"""""""""""""""""""""""""""""""""""""""""
# @author  sonus
# @date 02 - Apr - 2016
# @copyright sonus
# GitHub http://github.com/sonus21
"""""""""""""""""""""""""""""""""""""""""
from haystack import indexes
from twitt.models import Twit


class TwitIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    author = indexes.CharField(model_attr='author')
    pub_date = indexes.DateTimeField(model_attr='updated_on')



    def get_model(self):
        return Twit

    def index_queryset(self, using=None):
        return self.get_model().objects.all()


from django import forms

class SQLFileUploadForm(forms.Form):
    sql_file = forms.FileField(label="Upload SQL File")

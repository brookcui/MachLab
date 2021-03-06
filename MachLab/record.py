from django.contrib.auth.models import User
from MachLab.models import Userinfo, Model, Modelfile, ModelResult, ModelCommit, ModelPush, ModelPull, ModelDrop, Comment, Star
from django.core.files.base import ContentFile, File
import os
import zipfile
from MachLab.public import model_type_choices, icon_colors

def get_model_info(context, request, username, model_name):
    # User informtion #
    user = User.objects.get(username=username)
    context['email'] = user.email
    if user.userinfo:
        context['bio'] = user.userinfo.bio
        context['url'] = user.userinfo.url
        context['location'] = user.userinfo.location
        context['avatar'] = user.userinfo.avatar
        
    # Model information #
    model = Model.objects.filter(user=user, model_name=model_name).first()
    context['model'] = model

    # Star information #
    star = Star.objects.filter(model=model, user=request.user).first()
    if star is not None:
        context['star_type'] = 'unstar'
    else:
        context['star_type'] = 'star'

    # Modelfiles information #
    modelfiles = Modelfile.objects.filter(model=model)
    context['modelfiles'] = modelfiles

    # Latest Commit Information #
    commits = ModelCommit.objects.filter(user=user, model=model)
    latestCommit = commits.order_by('commit_datetime').last()
    context['latestCommit'] = latestCommit

    # Count #
    commit_count = commits.count()
    context['commit_count'] = commit_count
    upload_count = ModelPush.objects.filter(user=user, model=model).count()
    context['upload_count'] = upload_count
    download_count = ModelPull.objects.filter(user=user, model=model).count()
    context['download_count'] = download_count
    comment_count =  Comment.objects.filter(model=model).count()
    context['comment_count'] = comment_count

def get_model_modelfile(username, model_name, modelfile_filename):
    user = User.objects.get(username=username)
    model = Model.objects.filter(user=user, model_name=model_name).first()
    modelfile = Modelfile.objects.filter(model=model, filename=modelfile_filename).first()
    lines = modelfile.file.readlines()
    modelfile.lines_count = len(lines)
    modelfile.sloc_count = modelfile.lines_count
    for i in range(modelfile.lines_count):
        line_text = str(lines[i], encoding = "utf-8")
        if line_text in {'', ' ', '\r', '\n', '\r\n'}:
            modelfile.sloc_count -= 1
        lines[i] = line_text
    modelfile.text = lines
    modelfile.lines_range = range(modelfile.lines_count)
    modelfile.size = modelfile.file.size
    return model, modelfile

def download_model(request_username, username, model_name):
    user = User.objects.get(username=username)
    model = Model.objects.get(user=user, model_name=model_name)
    modelfiles = Modelfile.objects.filter(model=model)
    if modelfiles:
        data = get_zip_data(model.model_name, modelfiles)
        request_user = User.objects.get(username=request_username)
        model_pull = ModelPull.objects.create(model=model, user=request_user, description='user('+request_username+') download model('+model_name+')')
        model_pull.save()
        return data

def upload_modelfile(request_username, model_name, upload_file):
    user = User.objects.get(username=request_username)
    model = Model.objects.filter(user=user, model_name=model_name).first()
    filename = upload_file.name
    data = upload_file.file.read()
    file = ContentFile(data)
    modelfile = Modelfile.objects.create(model=model, filename=filename, description=filename)
    modelfile.file.save(filename, file)
    modelfile.save()
    model_push = ModelPush.objects.create(push_name='upload '+filename+' file(s) into '+model_name, model=model, user=user, description='upload modelfile')
    model_push.save()

def delete_modelfile(username, model_name, modelfile_filename):
    user = User.objects.get(username=username)
    model = Model.objects.filter(user=user, model_name=model_name).first()
    Modelfile.objects.filter(model=model, filename=modelfile_filename).delete()

def get_comment_list(context, model):
    comments = Comment.objects.filter(model=model)
    for comment in comments:
        comment.user.username = comment.user.username
        comment.user.avatar = comment.user.userinfo.avatar
        if comment.target is not None:
            comment.target.username = comment.target.user.username
    context['comments'] = comments

def record_click(request, username, model_name):
    if request.user.is_authenticated:
        user = User.objects.get(username=username)
        model = Model.objects.filter(user=user, model_name=model_name).first()
        model.click_count += 1
        model.save()

def record_star(request, username, model_name):
    user = User.objects.get(username=username)
    model = Model.objects.filter(user=user, model_name=model_name).first()
    user = User.objects.get(username=request.user.username)
    star = Star.objects.create(model=model, user=user)
    star.save()
    model.star_count += 1
    model.save()

def record_unstar(request, username, model_name):
    user = User.objects.get(username=username)
    model = Model.objects.filter(user=user, model_name=model_name).first()
    user = User.objects.get(username=request.user.username)
    Star.objects.filter(model=model, user=user).delete()
    if model.star_count >= 1:
        model.star_count -= 1
        model.save()

def record_new_comment(request_username, username, model_name, target_id, content):
    user = User.objects.get(username=username)
    model = Model.objects.get(user=user, model_name=model_name)
    request_user = User.objects.get(username=request_username)
    comments = Comment.objects.filter(model=model)
    target = None
    for comment in comments:
        if str(comment.id) == target_id:
            target = comment
            break
    comment = Comment.objects.create(model=model, user=request_user, target=target, content=content)
    comment.save()
    return model

def record_delete_comment(request_username, model_name):
    comment_to_delete = Comment.objects.get(id=int(comment_id))
    comment_to_delete.delete()

def get_n_top(n_top=12):
    models = Model.objects.all().order_by('-click_count')[0:n_top]
    for model in models:
        model.icon_color = icon_colors[model.model_type]
        model.model_type = model_type_choices[model.model_type][1]
    return models

def get_zip_data(zip_name, files):
    zip_name = zip_name +'.zip'
    zip_file = zipfile.ZipFile(zip_name, 'w')
    for file in files:
        f = open(file.filename, "wt")
        ff = file.file
        ff.open(mode='rt')
        data = ff.read()
        ff.close()
        f.write(data)
        f.close()
        zip_file.write(file.filename)
    zip_file.close()
    zip_file = open(zip_name, 'rb')
    data = zip_file.read()
    zip_file.close()
    
    for modelfile in modelfiles:
        os.remove(modelfile.filename)

    return data
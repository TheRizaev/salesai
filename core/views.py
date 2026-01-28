from django.shortcuts import render

def home(request):
    return render(request, 'index.html')

def pricing(request):
    return render(request, 'pricing.html')

def templates_view(request):
    return render(request, 'templates.html')

def docs(request):
    return render(request, 'docs.html')

def login_view(request):
    return render(request, 'login.html')
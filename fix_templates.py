import os
import glob

public_dir = '/Users/kavindunaveen/Desktop/Everbolt-Food-ERP/website/templates/public'

for filepath in glob.glob(os.path.join(public_dir, '*.html')):
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace extends
    content = content.replace('{% extends "base.html" %}', '{% extends "public/base.html" %}')
    content = content.replace("{% extends 'base.html' %}", '{% extends "public/base.html" %}')
    
    with open(filepath, 'w') as f:
        f.write(content)

print("Fixed templates.")

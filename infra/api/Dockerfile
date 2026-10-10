FROM langgenius/dify-api:1.17.1
COPY company_projects /app/api/company_projects
COPY company_members /app/api/company_members
COPY install.py /tmp/company-projects-install.py
RUN python /tmp/company-projects-install.py

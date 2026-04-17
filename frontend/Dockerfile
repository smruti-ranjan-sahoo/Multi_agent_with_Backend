FROM nginx:alpine

# Copy the Figma HTML files to
# the Nginx default web hosting directory
COPY figma_mock /usr/share/nginx/html

# Configure Nginx to listen on port 8501 (to match the old Streamlit setup)
# and set the default page to the Auth screen!
RUN echo 'server { \
    listen 8501; \
    location / { \
        root /usr/share/nginx/html; \
        index agentic_hub_auth.html index.html index.htm; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 8501

CMD ["nginx", "-g", "daemon off;"]

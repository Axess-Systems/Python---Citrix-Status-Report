import requests
from collections import defaultdict
import os
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def log_with_timestamp(message, level=logging.INFO):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.log(level, f"{timestamp} - {message}")

def fetch_data(url):
    log_with_timestamp(f"Fetching data from {url}")
    try:
        response = requests.get(url)
        response.raise_for_status()
        log_with_timestamp(f"Successfully fetched data from {url}")
        return response.json()
    except requests.RequestException as e:
        log_with_timestamp(f"Error fetching data from {url}: {e}", logging.ERROR)
        return {}

def get_region_services():
    log_with_timestamp("Getting region services")
    url = "https://status.cloud.com/api/connected_hub_services"
    data = fetch_data(url)
    region_services = {}
    for region in data:
        region_services[region['name']] = set(region['service_ids'])
    log_with_timestamp(f"Found {len(region_services)} regions")
    return region_services

def get_service_statuses():
    log_with_timestamp("Getting service statuses")
    url = "https://status.cloud.com/api/statuses"
    data = fetch_data(url)
    service_statuses = {}
    overall_status = {'all_up': True, 'count_status_1': 0, 'count_status_2': 0, 'count_status_3': 0}
    
    if 'groups' in data:
        for group in data['groups']:
            for service in group['services']:
                service_statuses[service['service_id']] = {
                    'name': service['service_name'],
                    'status': service['status']
                }
                if service['status'] == 1:
                    overall_status['count_status_1'] += 1
                elif service['status'] == 2:
                    overall_status['count_status_2'] += 1
                    overall_status['all_up'] = False
                elif service['status'] == 3:
                    overall_status['count_status_3'] += 1
                    overall_status['all_up'] = False
    
    log_with_timestamp(f"Found {len(service_statuses)} services")
    log_with_timestamp(f"Overall status: {'All up' if overall_status['all_up'] else 'Some services down'}")
    return service_statuses, overall_status

def create_report():
    log_with_timestamp("Creating report")
    region_services = get_region_services()
    service_statuses, overall_status = get_service_statuses()

    report = "<html><body>"
    report += "<h1>Citrix Service Status Summary</h1>"

    # Summary section
    report += "<h2>Summary:</h2>"
    report += f"<p>Total number of regions: {len(region_services)}</p>"
    report += f"<p>Total number of services: {len(service_statuses)}</p>"
    report += f"<p>Overall status: {'All services up' if overall_status['all_up'] else 'Some services are down'}</p>"

    report += "<h2>Overall Status:</h2>"
    report += f"<p>All services up: {overall_status['all_up']}</p>"
    report += f"<p>Services up: {overall_status['count_status_1']}</p>"
    report += f"<p>Services with issues: {overall_status['count_status_2']}</p>"
    report += f"<p>Services down: {overall_status['count_status_3']}</p>"

    report += "<h2>Services by Region:</h2>"
    for region, service_ids in region_services.items():
        report += f"<h3>{region}:</h3>"
        report += "<ul>"
        for service_id in service_ids:
            if service_id in service_statuses:
                service = service_statuses[service_id]
                status = "Up" if service['status'] == 1 else "Down"
                report += f"<li>{service['name']}: {status}</li>"
        report += "</ul>"

    report += "<h2>Detailed Status by Region:</h2>"
    for region, service_ids in region_services.items():
        report += f"<h3>{region}:</h3>"
        region_status = defaultdict(list)
        for service_id in service_ids:
            if service_id in service_statuses:
                service = service_statuses[service_id]
                status = "Up" if service['status'] == 1 else "Down"
                region_status[status].append(service['name'])

        report += f"<p>Services Up: {len(region_status['Up'])}</p>"
        report += f"<p>Services Down: {len(region_status['Down'])}</p>"
        if region_status['Up']:
            report += "<h4>Services Up:</h4>"
            report += "<ul>"
            for service in region_status['Up']:
                report += f"<li>{service}</li>"
            report += "</ul>"
        if region_status['Down']:
            report += "<h4>Services Down:</h4>"
            report += "<ul>"
            for service in region_status['Down']:
                report += f"<li>{service}</li>"
            report += "</ul>"

    report += "</body></html>"
    log_with_timestamp("Report created successfully")
    return report

def send_email(subject, body, recipients):
    log_with_timestamp(f"Sending email to {', '.join(recipients)}")
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT'))
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    use_tls = os.getenv('USE_TLS', 'False').lower() == 'true'

    msg = MIMEMultipart()
    msg['From'] = smtp_username
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if use_tls:
                server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        log_with_timestamp("Email sent successfully")
    except Exception as e:
        log_with_timestamp(f"Error sending email: {e}", logging.ERROR)

def main():
    log_with_timestamp("Starting Citrix Service Status Report script")
    report = create_report()
    log_with_timestamp("Saving report to file")
    
    # Save the report to a file
    with open("citrix_service_status_report.html", "w") as f:
        f.write(report)
    log_with_timestamp("Report saved to citrix_service_status_report.html")

    # Send email
    recipients = os.getenv('EMAIL_RECIPIENTS').split(',')
    subject = "Citrix Service Status Report"
    send_email(subject, report, recipients)

    log_with_timestamp("Script execution completed")

if __name__ == "__main__":
    main()
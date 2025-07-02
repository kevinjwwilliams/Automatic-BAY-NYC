import os
import logging
from dotenv import load_dotenv
from amadeus import Client, ResponseError
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Validate required environment variables
REQUIRED_ENV_VARS = [
    'AMADEUS_CLIENT_ID', 
    'AMADEUS_CLIENT_SECRET', 
    'SENDER_EMAIL', 
    'SENDER_EMAIL_PASSWORD', 
    'RECIPIENT_EMAIL'
]

def validate_env_vars():
    """Validate that all required environment variables are set."""
    missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('flight_notifier.log'),
        logging.StreamHandler()
    ]
)

# Configuration
CONFIG = {
    'ORIGIN_AIRPORTS': ['LGA', 'JFK'],
    'DESTINATION_AIRPORTS': ['OAK', 'SJC'],
    'AIRLINES': ['B6', 'UA', 'AA'],  # JetBlue, United, American
    'MAX_PRICE': 500,
    'DAYS_AHEAD': 1
}

class FlightNotifier:
    def __init__(self):
        try:
            self.amadeus = Client(
                client_id=os.getenv('AMADEUS_CLIENT_ID'),
                client_secret=os.getenv('AMADEUS_CLIENT_SECRET')
            )
        except Exception as e:
            logging.error(f"Failed to initialize Amadeus client: {e}")
            raise

    def search_flights(self):
        """Search for direct flights based on configuration"""
        found_flights = []
        search_date = (datetime.now() + timedelta(days=CONFIG['DAYS_AHEAD'])).strftime('%Y-%m-%d')

        for origin in CONFIG['ORIGIN_AIRPORTS']:
            for destination in CONFIG['DESTINATION_AIRPORTS']:
                try:
                    response = self.amadeus.shopping.flight_offers_search.get(
                        originLocationCode=origin,
                        destinationLocationCode=destination,
                        departureDate=search_date,
                        adults=1,
                        max=10,
                        nonStop=True,
                        includedAirlineCodes=','.join(CONFIG['AIRLINES']),
                        maxPrice=CONFIG['MAX_PRICE']
                    )
                    
                    if response.data:
                        logging.info(f"Found {len(response.data)} flights from {origin} to {destination}")
                        found_flights.extend(response.data)
                except ResponseError as error:
                    logging.error(f"Error searching flights from {origin} to {destination}: {error}")
        
        return found_flights

    def send_email(self, flights):
        """Send email notification about found flights"""
        if not flights:
            logging.info("No flights found. No email sent.")
            return

        try:
            msg = MIMEMultipart()
            msg['From'] = os.getenv('SENDER_EMAIL')
            msg['To'] = os.getenv('RECIPIENT_EMAIL')
            msg['Subject'] = f"Flight Alert: {len(flights)} Direct Flights Found!"
            
            body = "Direct Flights Found:\n\n"
            for flight in flights:
                body += f"From: {flight['originLocationCode']} To: {flight['destinationLocationCode']}\n"
                body += f"Airline: {flight['validatingAirlineCodes'][0]}\n"
                body += f"Price: ${flight['price']['total']}\n\n"
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(os.getenv('SMTP_SERVER', 'smtp.gmail.com'), 
                              int(os.getenv('SMTP_PORT', 587))) as server:
                server.starttls()
                server.login(os.getenv('SENDER_EMAIL'), os.getenv('SENDER_EMAIL_PASSWORD'))
                server.send_message(msg)
                logging.info("Email sent successfully!")
        except Exception as e:
            logging.error(f"Error sending email: {e}")

def main():
    try:
        validate_env_vars()
        notifier = FlightNotifier()
        flights = notifier.search_flights()
        notifier.send_email(flights)
    except Exception as e:
        logging.error(f"Unexpected error in main function: {e}")

if __name__ == "__main__":
    main()
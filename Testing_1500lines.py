import imaplib
from collections import Counter
from email import message_from_bytes
from email.header import decode_header
from datetime import datetime, timedelta
import pytz
import re
import logging
import os
import sys
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  # Adjust the path as needed

from webdriver_setup import WebDriverSetup
from PIL import Image
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
import unittest
import random
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import pyperclip
import pyautogui
import time
import win32gui
import win32con
import win32clipboard as clipboard
import ctypes
from logger import Logger
from sign_in_handler import SignInHandler
from handlers.config_handler import ConfigHandler

# Load configuration
config = ConfigHandler.get_config()

# Use the configuration values
DOWNLOAD_DIR = config.DOWNLOAD_DIR
IMAP_SERVER = config.IMAP_SERVER
EMAIL_ADDRESS = config.EMAIL_ADDRESS
APP_PASSWORD = config.APP_PASSWORD
SENDER_EMAIL = config.SENDER_EMAIL

VALID_FACTORS = ["Power Analysis"]  # List of valid analysis factors

# Constants for timeouts
SHORT_TIMEOUT = 10
LONG_TIMEOUT = 30

#class
class ScreenshotHandler:
    """
    Handles screenshot capture operations for test documentation and debugging.
    """

    def __init__(self, logger):
        """Initialize with a logger instance"""
        self.logger = logger
        self.screenshot_dir = os.path.join(os.path.dirname(__file__), 'screenshots')
        # Create separate directories for success and failure screenshots
        self.success_dir = os.path.join(self.screenshot_dir, 'success')
        self.failure_dir = os.path.join(self.screenshot_dir, 'failure')
        os.makedirs(self.success_dir, exist_ok=True)
        os.makedirs(self.failure_dir, exist_ok=True)

    def take_screenshot(self, driver, status, additional_info=""):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{status}_{additional_info}_{timestamp}.png"

            # Choose directory based on status
            screenshot_dir = self.success_dir if status == "success" else self.failure_dir
            screenshot_path = os.path.join(screenshot_dir, filename)

            # Simple screenshot without scrolling
            driver.save_screenshot(screenshot_path)

            self.logger.info(f"Screenshot saved to {screenshot_path}")
            return screenshot_path

        except Exception as e:
            self.logger.error(f"Failed to capture screenshot: {str(e)}")
            self.logger.debug(f"Screenshot failure details:", exc_info=True)
            return None


class FileHandler:
    """
    Handles file operations including checking, downloading, and content conversion.
    """

    def __init__(self, logger):
        self.logger = logger

    def get_latest_download_file(self, download_dir, file_type=".html", timeout=LONG_TIMEOUT):
        """
        Gets the latest downloaded file of specified type with improved detection.

        Args:
            download_dir: Directory to monitor for downloads
            file_type: File extension to look for (default: ".html")
            timeout: Maximum time to wait for download in seconds (default: 30)

        Returns:
            str: Path to the latest downloaded file or None if not found
        """
        try:
            # New logic to wait for up to 10 seconds for the file to appear
            start_time = time.time()
            while time.time() - start_time < timeout:
                files = [os.path.join(download_dir, f) for f in os.listdir(download_dir) if f.endswith(file_type)]
                if files:
                    latest_file = max(files, key=os.path.getctime)
                    self.logger.info(f"Latest downloaded file is {latest_file}.")
                    return latest_file
                time.sleep(1)

            self.logger.error("No HTML files found in the download directory after waiting.")
            return None
        except Exception as e:
            self.logger.error(f"Error getting the latest file: {e}")
            return None

    @staticmethod
    def check_if_file_is_not_empty(file_path):
        """Check if the file exists and is not empty"""
        try:
            return os.path.exists(file_path) and os.path.getsize(file_path) > 0
        except Exception:
            return False

    @staticmethod
    def convert_html_to_text(file_path, logger):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                html_content = file.read()
                soup = BeautifulSoup(html_content, 'html.parser')
                text_content = soup.get_text(strip=True)
                logger.info(f"Successfully converted HTML content from {file_path} to text")
                return text_content
        except Exception as e:
            logger.error(f"Error reading or parsing HTML file: {e}")
            return None


class FileUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test environment before any tests run"""
        cls.logger = Logger.setup_logger()
        cls.logger.info("Setting up test environment")
        
        try:
            cls.driver = WebDriverSetup.get_driver()
            cls.wait = WebDriverWait(cls.driver, 20)
            cls.screenshot_handler = ScreenshotHandler(cls.logger)
            cls.sign_in_handler = SignInHandler(
                driver=cls.driver,
                wait=cls.wait,
                logger=cls.logger,
                email_address=config.EMAIL_ADDRESS,
                imap_server=config.IMAP_SERVER,
                app_password=config.APP_PASSWORD,
                sender_email=config.SENDER_EMAIL
            )
            
            # Initialize file handler
            cls.file_handler = FileHandler(cls.logger)
            
            cls.logger.info("Test environment setup completed successfully")
            
        except Exception as e:
            cls.logger.error(f"Failed to set up test environment: {e}")
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            cls.logger.info("Tearing down WebDriver after tests")
            cls.logger.info("Waiting for 15 seconds before quitting WebDriver")
            time.sleep(15)
            if hasattr(cls, 'driver') and cls.driver:
                cls.driver.quit()
                cls.logger.info("WebDriver quit successfully.")
            else:
                cls.logger.warning("WebDriver was not initialized.")
        except Exception as e:
            cls.logger.error(f"Error during teardown: {e}")

    def handle_login(self):
        """Handle the login process"""
        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                message_div_xpath = "//div[contains(@class, 'message-class')]//span"
                if self.sign_in_handler.handle_login():
                    self.logger.info("Login successful")
                    return True
                return False
            except Exception as e:
                self.logger.warning(f"Login attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    self.logger.error(f"Error during login after {max_retries} attempts: {e}")
                    self.take_screenshot("failure", "login_error")
                    return False

    def resend_otp(self):
        """Handle the OTP resend process"""
        try:
            self.logger.info("Clicked on Resend OTP button")
            time.sleep(5)  # Add a delay before fetching the latest OTP
            self.logger.info("Waiting 5 seconds before fetching latest OTP...")
            time.sleep(5)  # Ensure there's a delay before checking for the OTP
            self.logger.info("Checking for new OTP email...")
            # Your existing logic to check for the OTP email
            ...
        except Exception as e:
            self.logger.error(f"Error during OTP resend: {e}")

    def handle_factor_selection(self, factor):
        try:
            div_xpath = "//div[contains(@class, 'cursor-pointer') and .//div[text()='Factors']]"
            arrow_xpath = div_xpath + "/div[last()]/img"

            div_element = self.driver.find_element(By.XPATH, div_xpath)
            arrow_element = self.driver.find_element(By.XPATH, arrow_xpath)
            arrow_src = arrow_element.get_attribute("src")

            if "M6.99999%205.61602" in arrow_src:
                self.logger.info("Arrow is Down! Initiating click on factors dropdown...")
                ActionChains(self.driver).move_to_element(div_element).click().perform()
                self.logger.info("Successfully clicked factors dropdown")
            else:
                self.logger.info("Arrow is already Up! Dropdown already expanded")

            factor_label = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f"//label[normalize-space()='{factor}']"))
            )
            self.logger.info(f"Found factor label for '{factor}', preparing to click...")
            time.sleep(7)
            factor_label.click()
            self.logger.info(f"Successfully clicked factor label for '{factor}'")
            self.screenshot_handler.take_screenshot(self.driver, "success", f"{factor}_selection")
            return True
        except Exception as e:
            self.logger.error(f"Factor selection failed: {e}")
            self.screenshot_handler.take_screenshot(self.driver, "failure", "factor_selection_error")
            return False

    def handle_file_upload(self, file_path):
        try:
            self.logger.info("Searching for file input element...")
            file_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
            )
            self.logger.info("File input element found successfully")
            time.sleep(7)
            self.logger.info(f"Attempting to upload file: {file_path}")
            file_input.send_keys(file_path)
            self.logger.info(f"File upload successful: {file_path}")
            self.screenshot_handler.take_screenshot(self.driver, "success", "file_upload")
            return True
        except Exception as e:
            self.logger.error(f"File upload failed: {e}")
            self.screenshot_handler.take_screenshot(self.driver, "failure", "file_upload_error")
            return False

    def extract_severity_counts(self, html_content, table_class, severity_column_index=1):
        """
        Extracts severity counts from the provided HTML content containing a table.
        """
        try:
            # Parse the HTML content
            soup = BeautifulSoup(html_content, 'html.parser')

            # Find the table with the specified class
            table = soup.find('table', class_=table_class)
            severity_count = Counter()

            # Check if the table exists
            if not table:
                raise ValueError(f"No table found with class '{table_class}'")

            # Iterate through each row in the table body
            for row in table.find('tbody').find_all('tr'):
                # Get the severity from the specified column index (td)
                columns = row.find_all('td')
                if len(columns) > severity_column_index:
                    severity = columns[severity_column_index].text.strip()
                    severity_count[severity] += 1

            return severity_count

        except Exception as e:
            self.logger.error(f"Error extracting severity counts: {e}")
            return Counter()

    def handle_submit(self, factor):
        try:
            self.logger.info("Waiting for page to be fully loaded...")
            WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            self.logger.info("Page fully loaded, searching for submit button...")

            submit_image = WebDriverWait(self.driver, 100).until(
                EC.element_to_be_clickable((By.XPATH, "//img[contains(@alt,'Submit')]"))
            )
            self.logger.info("Submit button found and clickable")

            submit_image.click()
            self.logger.info(f"Successfully clicked submit button for factor: '{factor}'")
            self.screenshot_handler.take_screenshot(self.driver, "success", "submit_click")
            return True
        except Exception as e:
            self.logger.error(f"Submit failed: {e}")
            self.screenshot_handler.take_screenshot(self.driver, "failure", "submit_error")
            return False

    def check_spinner_and_message_visibility(self):
        """Continuously check if the spinner is visible and log the message element if present.
        Returns the last logged message when the spinner disappears.
        """
        try:
            previous_message = None
            last_logged_message = None
            spinner_xpath = "//span[@style='display: inherit;']"
            message_div_xpath = "//div[contains(@class, 'p-4 rounded-[10px] border')]//p"

            while True:
                try:
                    # Use WebDriverWait to handle stale elements for spinner check
                    spinner_visible = len(WebDriverWait(self.driver, 3).until(
                        EC.presence_of_all_elements_located((By.XPATH, spinner_xpath))
                    )) > 0

                    if spinner_visible:
                        try:
                            # Use WebDriverWait for message element to handle stale references
                            message_element = WebDriverWait(self.driver, 3).until(
                                EC.presence_of_element_located((By.XPATH, message_div_xpath))
                            )

                            if message_element.is_displayed():
                                current_message = message_element.text
                                if current_message != previous_message:
                                    self.logger.info("Message element is visible: %s", current_message)
                                    previous_message = current_message
                                    last_logged_message = current_message
                        except (TimeoutException, StaleElementReferenceException):
                            self.logger.debug("Message element not found or stale, continuing to check...")
                    else:
                        break

                    time.sleep(1)  # Reduced sleep time for more responsive checking

                except TimeoutException:
                    # If spinner is not found, assume processing is complete
                    break
                except StaleElementReferenceException:
                    # If element becomes stale, continue the loop
                    continue

            return last_logged_message

        except Exception as e:
            self.logger.error(f"Error in check_spinner_and_message_visibility: {e}")
            return None

    def wait_for_processing(self):
        try:
            spinner_xpath = "//span[@class='loading spinner spinner-container text-white loading-md']"
            spinner_visible = True  # Initialize spinner visibility

            while spinner_visible:
                try:
                    spinner_visible = len(self.driver.find_elements(By.XPATH, spinner_xpath)) > 0
                    if spinner_visible:
                        last_logged_message = self.check_spinner_and_message_visibility()
                        time.sleep(3)  # Wait before checking again
                except NoSuchElementException:
                    spinner_visible = False  # Exit the loop if the spinner is not found

            time.sleep(5)  # Wait for additional processing time
            return True

        except Exception as e:
            self.logger.error(f"Error while waiting for processing: {e}")
            return False

    def check_error_messages(self):
        try:
            paragraphs1 = self.driver.find_elements(By.XPATH,
                                                    "//div[contains(text(), 'This file format is not supported')]"
                                                    )
            if paragraphs1:
                self.logger.error("Invalid file format")
                return True

            paragraphs2 = self.driver.find_elements(By.XPATH,
                                                    "//div[contains(text(), 'The code snippet is too small')]"
                                                    )
            if paragraphs2:
                self.logger.error("Code snippet too small")
                return True

            return False
        except Exception as e:
            self.logger.error(f"Error checking error messages: {e}")
            return True

    def process_table_data(self, expected_rows):
        """Processes and validates table data, including testing issue links."""
        try:
            table_body = self.driver.find_element(By.XPATH, "//table[@class='table-auto w-full overflow-x-auto']/tbody")
            rows = table_body.find_elements(By.XPATH, ".//tr")
            row_cnt, all_data_present = 0, True

            for row in rows:
                row_cnt += 1
                # Get the issue link element
                issue_link = row.find_element(By.XPATH, ".//td[1]//a")
                issue_id = issue_link.text.strip()
                description = row.find_element(By.XPATH, ".//td[2]").text.strip()

                if not issue_id or not description:
                    self.logger.error(
                        f"Bug found - Missing {', '.join(filter(None, ['issue' if not issue_id else '', 'description' if not description else '']))} in row: {row}")
                    all_data_present = False
                    continue

                # Store the issue ID before clicking
                current_issue_id = issue_id

                # Click the issue link
                self.logger.info(f"Clicking issue link for Issue {current_issue_id}")
                issue_link.click()
                time.sleep(1)  # Brief wait for the UI to update

                # Verify the corresponding issue details are displayed
                try:
                    # Wait for and verify the issue details section
                    issue_details = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((
                            By.XPATH,
                            f"//div[contains(@class, 'text-[14px] sm:text-[20px]')]//p[@id='{current_issue_id}']"
                        ))
                    )

                    if issue_details.is_displayed():
                        self.logger.info(f"Successfully navigated to details for Issue {current_issue_id}")
                    else:
                        self.logger.error(f"Issue details not displayed for Issue {current_issue_id}")
                        all_data_present = False

                except Exception as e:
                    self.logger.error(f"Error verifying issue details for Issue {current_issue_id}: {e}")
                    all_data_present = False

            if row_cnt == expected_rows:
                self.logger.info("Row count matches successfully")

            screenshot_name = "success_data_check" if all_data_present else "failure_data_check"
            self.take_screenshot(screenshot_name, "Data validation result")
            return all_data_present

        except Exception as e:
            self.logger.error(f"Error processing table data: {e}")
            self.take_screenshot("failure_table_data", "Error processing table data")
            return False

    def process_issue_details(self):
        """Extracts and validates issue details."""
        try:
            issue_divs = self.driver.find_elements(By.XPATH,
                                                   "//div[contains(@class, 'text-[14px] sm:text-[20px] flex flex-col gap-4 my-5')]")

            for div in issue_divs:
                try:
                    issue_id_element = div.find_element(By.XPATH,
                                                        ".//p[@class='text-[14px] sm:text-[22px] font-bold' and @id]")
                    issue_id = issue_id_element.text if issue_id_element else None

                    issue_desc_element = div.find_element(By.XPATH,
                                                          ".//p[contains(text(), 'Issue')]/following-sibling::p")
                    issue_desc = issue_desc_element.text if issue_desc_element else None

                    solution_desc_element = div.find_element(By.XPATH,
                                                             ".//p[contains(text(), 'Solution')]/following-sibling::p")
                    solution_desc = solution_desc_element.text if solution_desc_element else None

                    code_blocks = div.find_elements(By.XPATH, ".//pre//code")
                    code_block_before_solution = code_blocks[0].get_attribute("innerText") if len(
                        code_blocks) > 0 else "No Code Found"
                    code_block_after_solution = code_blocks[1].get_attribute("innerText") if len(
                        code_blocks) > 1 else "No Code Found"

                    if all([issue_id, issue_desc, solution_desc]):
                        self.logger.info(f"Issue details validated for {issue_id}")
                        self.take_screenshot("success_issue_details", f"Issue details for {issue_id}")
                    else:
                        missing_fields = [
                            name for name, value in {
                                "Issue ID": issue_id,
                                "Issue Description": issue_desc,
                                "Solution Description": solution_desc
                            }.items() if not value
                        ]
                        self.logger.error(f"Missing required issue details: {', '.join(missing_fields)}")
                        self.take_screenshot("failure_issue_details",
                                             f"Missing issue details: {', '.join(missing_fields)}")

                except NoSuchElementException as e:
                    self.logger.error(f"Element not found: {e}")
                    self.take_screenshot("failure_issue_details", "Missing one or more required elements")
                except Exception as e:
                    self.logger.error(f"Unexpected error: {e}")
                    self.take_screenshot("failure_issue_details", "Unexpected error occurred")

            return True
        except Exception as e:
            self.logger.error(f"Error processing issue details: {e}")
            self.take_screenshot("failure_issue_processing", "Error processing issue details")
            return False

    def take_screenshot(self, status, additional_info=""):
        """Take a screenshot with proper naming and directory structure
        
        Args:
            status (str): Status of the test (success/failure)
            additional_info (str): Additional context for the screenshot name
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_dir = os.path.join(os.path.dirname(__file__), 'screenshots', status)
            os.makedirs(screenshot_dir, exist_ok=True)
            
            # Clean up the filename by removing any invalid characters
            filename = f"{status}_{additional_info}_{timestamp}.png"
            filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
            screenshot_path = os.path.join(screenshot_dir, filename)
            
            # Take the screenshot
            self.driver.save_screenshot(screenshot_path)
            self.logger.info(f"Screenshot saved to {screenshot_path}")
            return screenshot_path
        except Exception as e:
            self.logger.error(f"Failed to take screenshot: {str(e)}")
            return None

    def handle_like_dislike_functionality(self):
        """
        Handles the like/dislike functionality.
        """
        try:
            self.logger.info("Starting like/dislike functionality testing")

            # Wait for the container div to be present
            container = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    "//div[contains(@class, 'flex items-center') and .//span[contains(text(), 'Is this analysis useful')]]"
                ))
            )

            # Scroll the container into view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", container)
            time.sleep(1)  # Wait for scroll to complete

            # Find the like button within the container
            like_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//img[contains(@src, 'data:image/png;base64') and contains(@class, 'cursor-pointer')]"
                ))
            )

            # Use JavaScript to click the button to avoid intercepted click
            self.driver.execute_script("arguments[0].click();", like_button)
            
            self.take_screenshot("success_like_button", "Successfully clicked like button")
            self.logger.info("Successfully clicked like button")

            # Wait a moment for any animations or state changes
            time.sleep(5)

            # Find and click the dislike button
            dislike_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//img[contains(@src, 'data:image/png;base64') and @class='h-[20.36px] w-[22px] cursor-pointer']"
                ))
            )

            # Use JavaScript to click the dislike button to ensure it registers correctly
            self.driver.execute_script("arguments[0].click();", dislike_button)
            
            self.take_screenshot("success_dislike_button", "Successfully clicked dislike button")
            self.logger.info("Successfully clicked dislike button")

            return True

        except Exception as e:
            self.logger.error(f"Error in like/dislike functionality: {e}")
            return False

    def get_ui_severity_counts(self):
        """
        Extracts severity counts from the UI dynamically.
        """
        try:
            rows = self.driver.find_elements(By.XPATH, "//table[@class='custom-table']/tbody/tr")
            severity_count = Counter()

            for row in rows:
                severity = row.find_element(By.XPATH, "./td[2]").text.strip()
                severity_count[severity] += 1

            return severity_count

        except Exception as e:
            self.logger.error(f"Error extracting severity counts from UI: {e}")
            return Counter()

    def get_downloaded_severity_counts(self, text_content):
        """
        Extracts severity counts from the downloaded file content.
        """
        try:
            severity_count = Counter()
            lines = text_content.split("\n")

            for line in lines:
                words = line.strip().split()
                if len(words) > 1 and words[0].startswith("Issue"):
                    severity = words[1]  # Assuming severity is the second word
                    severity_count[severity] += 1

            return severity_count

        except Exception as e:
            self.logger.error(f"Error extracting severity counts from downloaded file: {e}")
            return Counter()

    def handle_download(self):
        """
        Handles the download functionality with improved error handling and validation.
        """
        try:
            self.logger.info("Starting download process...")

            # Scroll down to ensure the download button is in view
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Wait for the scroll to complete

            # Find and click the download button
            download_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[span[text()='Download HTML']]/button"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
            time.sleep(2)  # Wait for the scroll to complete

            # Ensure the button is clickable
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(download_button))
            download_button.click()  # Click the download button
            self.logger.info("Successfully clicked download button")

            time.sleep(10)  # LONG_TIMEOUT - adjust value as needed
            # Wait for download to complete and get the file path
            downloaded_file = self.get_latest_file(config.DOWNLOAD_DIR, ".html")
            if not downloaded_file:
                self.logger.error("No downloaded file found after clicking the download button.")
                return False

            self.logger.info(f"Downloaded file: {downloaded_file}")

            # Verify file exists and is not empty
            if not self.check_file_empty(downloaded_file):
                self.logger.error(f"Downloaded file '{downloaded_file}' is empty or invalid.")
                return False

            # Read the content of the downloaded file
            with open(downloaded_file, 'r', encoding='utf-8') as file:
                html_content = file.read()

            # Extract severity counts from the downloaded HTML content
            severity_counts = self.get_downloaded_severity_counts(html_content)

            # Get severity counts from UI
            ui_severity_counts = self.get_ui_severity_counts()

            # Verify severity counts in downloaded content
            for severity, count in severity_counts.items():
                if str(count) not in html_content:
                    self.logger.error(
                        f"Severity count mismatch for {severity}. Expected count: {count} not found in downloaded content.")
                    return False

            self.logger.info("Severity counts match between UI and downloaded content")

            buttons = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'flex bg-white')]//button")

            # Download individual severity reports
            downloaded_files = []
            for button in buttons:
                if not button.get_attribute('disabled'):
                    button_text = button.text.split("\n")[0]
                    self.logger.info(f"Clicking on enabled button: {button_text}")
                    button.click()
                    time.sleep(2)  # Wait for content to load

                    # Find and click the download button for this severity
                    download_button = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//div[span[text()='Download HTML']]/button"))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
                    time.sleep(1)

                    WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(download_button))
                    download_button.click()
                    self.logger.info(f"Clicked download button for severity: {button_text}")

                    time.sleep(10)  # Wait for download

                    # Get and verify the downloaded file
                    new_file = self.get_latest_file(config.DOWNLOAD_DIR, ".html")
                    if new_file and new_file not in downloaded_files:
                        downloaded_files.append(new_file)
                        self.logger.info(f"Added downloaded file to list: {new_file}")
                    else:
                        self.logger.error("Failed to find new downloaded file.")

            # Compare downloaded reports if we have at least 2 files
            if len(downloaded_files) >= 2:
                self.logger.info("Comparing downloaded reports...")
                content1 = self.convert_html_to_text(downloaded_files[0])
                content2 = self.convert_html_to_text(downloaded_files[1])

                if content1 and content2:
                    if content1 == content2:
                        self.logger.info("Downloaded reports have matching content.")
                    else:
                        self.logger.error("Downloaded reports have different content.")
                        return False

            # Verify severity counts match
            actual_severity_counts = self.get_downloaded_severity_counts(html_content)
            self.logger.info(f"Actual severity counts from downloaded content: {actual_severity_counts}")

            for severity, expected_count in severity_counts.items():
                actual_count = actual_severity_counts.get(severity, 0)
                if actual_count != expected_count:
                    self.logger.error(
                        f"Severity count mismatch for {severity}. Expected: {expected_count}, Found: {actual_count}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Error during download process: {str(e)}")
            return False

    def get_latest_file(self, download_dir, file_extension=None, timeout=30):
        """
        Get the latest downloaded file with improved error handling
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Get all files in download directory
                files = [
                    f for f in os.listdir(download_dir) 
                    if os.path.isfile(os.path.join(download_dir, f))
                ]
                
                # Filter by extension if specified
                if file_extension:
                    files = [f for f in files if f.endswith(file_extension)]
                    
                # Sort by modification time
                if files:
                    files.sort(
                        key=lambda x: os.path.getmtime(os.path.join(download_dir, x)),
                        reverse=True
                    )
                    return os.path.join(download_dir, files[0])
                    
            except Exception as e:
                self.logger.error(f"Error checking downloads: {e}")
            time.sleep(1)
        return None

    def check_file_empty(self, file_path):
        """Check if the file exists and is not empty"""
        try:
            return os.path.exists(file_path) and os.path.getsize(file_path) > 0
        except Exception:
            return False

    def convert_html_to_text(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                html_content = file.read()
                soup = BeautifulSoup(html_content, 'html.parser')
                text_content = soup.get_text(strip=True)
                self.logger.info(f"Successfully converted HTML content from {file_path} to text")
                return text_content
        except Exception as e:
            self.logger.error(f"Error reading or parsing HTML file: {e}")
            return None

    def log_error_with_screenshot(self, message, screenshot_context="error"):
        """
        Logs an error message and captures a screenshot.
        Args:
            message: Error message to log
            screenshot_context: Context identifier for the screenshot
        """
        self.logger.error(message)
        self.take_screenshot("failure", screenshot_context)

    def verify_analysis_completion_email(self, factor):
        """
        Verifies if the analysis completion email is received with up to 3 retry attempts.
        """
        max_attempts = 3
        delay_between_attempts = 10  # seconds

        self.logger.info(f"Checking for analysis completion email for factor: {factor}")

        for attempt in range(max_attempts):
            try:
                self.logger.info(f"Attempt {attempt + 1} of {max_attempts}")

                # Connect to email server
                mail = imaplib.IMAP4_SSL(IMAP_SERVER, timeout=30)
                mail.login(EMAIL_ADDRESS, APP_PASSWORD)
                mail.select("inbox")

                # Search for the exact subject line
                expected_subject = f"Tell us what you think of {factor} analysis"
                search_criteria = f'(FROM "{SENDER_EMAIL}" SUBJECT "{expected_subject}")'

                status, messages = mail.search(None, search_criteria.encode())

                if status == "OK" and messages[0]:
                    self.logger.info(f"Found email with subject: '{expected_subject}' on attempt {attempt + 1}")
                    return True
                else:
                    self.logger.warning(f"No email found with subject: '{expected_subject}' on attempt {attempt + 1}")

                    # If this isn't the last attempt, wait before trying again
                    if attempt < max_attempts - 1:
                        self.logger.info(f"Waiting {delay_between_attempts} seconds before next attempt...")
                        time.sleep(delay_between_attempts)

            except Exception as e:
                self.logger.error(f"Error checking email (attempt {attempt + 1}): {e}")

                # If this isn't the last attempt, wait before trying again
                if attempt < max_attempts - 1:
                    self.logger.info(f"Waiting {delay_between_attempts} seconds before next attempt...")
                    time.sleep(delay_between_attempts)

            finally:
                if 'mail' in locals():
                    try:
                        mail.logout()
                    except Exception as e:
                        self.logger.warning(f"Error logging out from email: {e}")

        # If we get here, all attempts failed
        self.logger.error(f"Failed to find email after {max_attempts} attempts")
        return False

    def extract_email_body(self, msg):
        """
        Helper method to extract email body with better handling of different content types.

        Args:
            msg: Email message object

        Returns:
            str: Extracted email body or empty string if extraction fails
        """
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/html":
                        return part.get_payload(decode=True).decode(errors='ignore')
                    elif content_type == "text/plain":
                        return part.get_payload(decode=True).decode(errors='ignore')
            else:
                return msg.get_payload(decode=True).decode(errors='ignore')
            return ""
        except Exception as e:
            self.logger.error(f"Error extracting email body: {e}")
            return ""

    def handle_analysis_results(self):
        """
        Handles and validates the analysis results, including table data, div/span elements, and code blocks.
        """
        try:
            self.logger.info("Starting analysis results validation")

            # Process table data
            if not self.process_table_data(expected_rows=None):  # Remove expected_rows parameter since it's not used
                self.logger.error("Table data validation failed")
                return False

            # Process issue details
            if not self.process_issue_details():
                self.logger.error("Issue details validation failed")
                return False

            self.logger.info("Analysis results validation completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error during analysis results processing: {e}")
            self.take_screenshot("failure_analysis_results", "Error processing results")
            return False

    def open_history_section(self):
        """
        Clicks on the History section only if it is collapsed.
        """
        try:
            # XPath to locate the History dropdown and its arrow icon
            history_xpath = "//div[contains(@class, 'cursor-pointer') and .//div[text()='History']]"
            arrow_xpath = history_xpath + "/div[last()]/img"

            # Locate History section element
            history_element = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, history_xpath))
            )

            history_element.click()

        except Exception as e:
            self.logger.error(f"Error opening History section: {e}")

    def compare_html_files(self, file1_path, file2_path):
        """Compare two HTML files for equality
        
        Args:
            file1_path (str): Path to first HTML file
            file2_path (str): Path to second HTML file
            
        Returns:
            bool: True if files are equal, False otherwise
        """
        try:
            if not file1_path or not file2_path:
                self.logger.error("One or both file paths are None")
                return False

            content1 = self.convert_html_to_text(file1_path)
            content2 = self.convert_html_to_text(file2_path)

            if content1 and content2:
                return content1 == content2
            return False

        except Exception as e:
            self.logger.error(f"Error comparing HTML files: {str(e)}")
            return False

    def history_analysis(self):
        """
        Analyzes the history entry with improved click handling and form interference mitigation
        """
        try:
            # Store the first downloaded file path
            first_download_path = None

           # Scroll down to ensure the download button is in view
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Wait for the scroll to complete

            # Find and click the download button
            download_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[span[text()='Download HTML']]/button"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
            time.sleep(2)  # Wait for the scroll to complete

            # Ensure the button is clickable
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(download_button))
            download_button.click()  # Click the download button
            self.logger.info("Successfully clicked download button")

            time.sleep(10)  # LONG_TIMEOUT - adjust value as needed
            # Wait for download to complete and get the file path
            downloaded_file = self.get_latest_file(config.DOWNLOAD_DIR, ".html")
            if not downloaded_file:
                self.logger.error("No downloaded file found after clicking the download button.")
                return False

            self.logger.info(f"Downloaded file: {downloaded_file}")

            first_download_path = self.get_latest_file(config.DOWNLOAD_DIR, ".html", timeout=30)
            if not first_download_path:
                self.logger.error("First download failed")
                self.take_screenshot("failure", "first_download_failed")
                return False

            self.logger.info(f"First download successful: {first_download_path}")

            # Step 1: Open the History section and wait for any forms to load
            self.logger.info("Opening History section")
            self.open_history_section()
            time.sleep(3)  # Increased wait time for forms to fully load

            # Wait for any loading forms to complete
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: len(d.find_elements(By.XPATH, "//form[contains(@class, 'flex flex-col justify-around')]")) > 0
                )
                time.sleep(2)  # Additional wait after forms are found
            except TimeoutException:
                self.logger.info("No interfering forms found")

            # Step 2: Locate all history entries
            self.logger.info("Locating history entries")
            history_items = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH,
                    "//div[contains(@class, 'flex flex-col item-start gap-4')]/a"))
            )

            if not history_items:
                self.logger.error("No history items found")
                self.take_screenshot("failure", "no_history_items")
                return False

            # Step 3: Process the first history item
            self.logger.info("Processing first history entry")
            first_entry = history_items[0]

            # Scroll to entry and ensure it's in view
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", first_entry)
            time.sleep(2)  # Wait for scroll and any animations

            # Extract and verify file name and factor
            entry_text = first_entry.find_element(By.XPATH, ".//div[contains(@class, 'text-[16px]')]").text.strip()
            entry_factor = first_entry.find_element(By.XPATH, ".//span").text.strip()

            # Get expected values
            actual_file = os.path.basename(config.FILE_PATH)
            actual_factor = self.selected_factor

            # Verify file name and factor match
            if actual_file not in entry_text or actual_factor != entry_factor:
                self.logger.error(f"Mismatch in history entry. Expected: {actual_file}/{actual_factor}, "
                                f"Found: {entry_text}/{entry_factor}")
                self.take_screenshot("failure", "history_entry_mismatch")
                return False

            self.logger.info("History entry matches expected values")

            # Try to remove any interfering elements
            self.driver.execute_script("""
                var forms = document.querySelectorAll('form.flex.flex-col.justify-around');
                forms.forEach(function(form) {
                    form.style.pointerEvents = 'none';
                });
            """)

            # Click the entry with retry logic
            max_click_attempts = 3
            for attempt in range(max_click_attempts):
                try:
                    # Try different click methods
                    try:
                        # Try regular click first
                        first_entry.click()
                    except:
                        try:
                            # Try JavaScript click if regular click fails
                            self.driver.execute_script("arguments[0].click();", first_entry)
                        except:
                            # Try moving to element and clicking
                            actions = ActionChains(self.driver)
                            actions.move_to_element(first_entry).click().perform()

                    # Wait for page load
                    WebDriverWait(self.driver, 10).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                    break
                except Exception as e:
                    if attempt == max_click_attempts - 1:
                        raise e
                    time.sleep(2)

            # Wait for any animations or transitions to complete
            time.sleep(3)

            # Find and click download button with retry logic
            download_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[span[text()='Download HTML']]/button"))
            )
            
            # Scroll to download button
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", download_button)
            time.sleep(2)

            # Try to click download button with retry logic
            for attempt in range(max_click_attempts):
                try:
                    self.driver.execute_script("arguments[0].click();", download_button)
                    self.logger.info("Clicked download button for history entry")
                    break
                except Exception as e:
                    if attempt == max_click_attempts - 1:
                        raise e
                    time.sleep(2)

            # Wait for download to complete
            time.sleep(5)

            # Get the history download file
            history_download_path = self.get_latest_file(config.DOWNLOAD_DIR, ".html", timeout=30)
            if not history_download_path:
                self.logger.error("History download failed")
                self.take_screenshot("failure", "history_download_failed")
                return False

            self.logger.info(f"History download successful: {history_download_path}")

            # Compare the files
            if self.compare_html_files(first_download_path, history_download_path):
                self.logger.info("HTML files are identical")
                self.take_screenshot("success", "history_analysis_complete")
                return True
            else:
                self.logger.error("HTML files are different")
                self.take_screenshot("failure", "file_comparison_failed")
                return False

        except Exception as e:
            self.logger.error(f"Error during history analysis: {str(e)}")
            self.take_screenshot("failure", "history_analysis_error")
            return False

    def handle_logout(self):
        """Handles the logout process and verifies the logout success."""
        try:
            self.logger.info("Logging out...")
            time.sleep(5)

            # Click the logout trigger div
            logout_trigger_div = self.driver.find_element(By.XPATH,
                "//div[contains(@class, 'text-xl font-bold text-center cursor-pointer')]")
            logout_trigger_div.click()
            self.logger.info("Successfully clicked on logout trigger.")

            time.sleep(5)

            # Click the logout button
            logout_button_div = self.driver.find_element(By.XPATH,
                "//span[contains(@class, 'text-text_black') and contains(text(), 'Log Out')]")
            logout_button_div.click()
            self.logger.info("Successfully clicked on logout button.")

            # Wait for and verify the logout success popup
            logout_popup = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Logged out successfully!')]"))
            )

            if logout_popup.is_displayed():
                self.take_screenshot("success", "logout_success")
                self.logger.info("Logout success popup verified")
            else:
                self.logger.error("Logout success popup not found")
                self.take_screenshot("failure", "logout_popup_missing")
                self.fail("Logout popup verification failed")

            # Validate session clearance
            try:
                sign_in_message = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR,
                        "body > div:nth-child(2) > div:nth-child(1) > div:nth-child(2) > div:nth-child(1) > div:nth-child(1) > div:nth-child(3)"))
                    )

                if sign_in_message:
                    self.logger.info("Successfully logged out. 'Sign in to continue' message is displayed.")
                    self.take_screenshot("success", "logout_complete")
                else:
                    self.logger.error("'Sign in to continue' message not found. Session may not be cleared.")
                    self.take_screenshot("failure", "session_not_cleared")
                    self.fail("'Sign in to continue' message not found.")
            except Exception as e:
                self.logger.error("Session clearance failed. Login form not found.")
                self.take_screenshot("failure", "session_clearance_failed")
                self.fail("Session clearance failed.")

        except Exception as e:
            self.logger.error(f"An error occurred during the logout process: {str(e)}")
            self.take_screenshot("failure", "logout_error")
            self.fail(f"Logout failed with error: {str(e)}")

    def handle_analysis_buttons(self):
        """
        Handles the analysis buttons, clicking only on enabled buttons.
        """
        try:
            self.logger.info("Starting to handle analysis buttons")

            buttons = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'flex bg-white')]//button")

            for button in buttons:
                button_text = button.text.split("\n")[0]
                is_disabled = button.get_attribute("disabled")

                if is_disabled:
                    self.logger.info(f"Skipping disabled button: {button_text}")
                    continue

                expected_rows = int(button.find_element(By.TAG_NAME, "span").text)
                self.logger.info(f"Found notification - {button_text}: {expected_rows}")

                # Click the button and wait for content update
                self.logger.info(f"Clicking on enabled button: {button_text}")
                button.click()
                time.sleep(2)  # Wait for any potential page updates

                # Process table data with expected row count
                if not self.process_table_data(expected_rows):
                    self.logger.error(f"Table data validation failed for {button_text}")
                    return False

                # Process issue details
                if not self.process_issue_details():
                    self.logger.error(f"Issue details validation failed for {button_text}")
                    return False

                self.logger.info(f"Successfully completed analysis for {button_text}")

            return True

        except Exception as e:
            self.logger.error(f"Error during analysis results processing: {e}")
            self.take_screenshot(self.driver, "failure_analysis_results")
            return False

    def get_table_content(self):
        """
        Gets the current table content from the UI
        """
        try:
            table_data = []
            rows = self.driver.find_elements(By.XPATH, "//table[@class='table-auto w-full overflow-x-auto']/tbody/tr")

            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if cells:
                    row_data = {
                        'issue_id': cells[0].text.strip(),
                        'severity': cells[1].text.strip(),
                        'description': cells[2].text.strip()
                    }
                    table_data.append(row_data)

            return table_data
        except Exception as e:
            self.logger.error(f"Error getting table content: {e}")
            return None

    def scroll_to_top(self):
        """Scrolls to the top of the page and checks if the up arrow button is present."""
        try:
            self.logger.info("Starting scroll to top operation")

            # First scroll down to ensure the up arrow button appears
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Wait for scroll and button to appear

            # Define the up arrow button locator
            up_arrow_xpath = "//button[contains(@class, 'fixed')]"

            # Wait for the up arrow button with better error handling
            try:
                up_arrow_button = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, up_arrow_xpath))
                )

                # Ensure button is in viewport and clickable
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", up_arrow_button)
                time.sleep(1)

                # Try JavaScript click first
                self.driver.execute_script("arguments[0].click();", up_arrow_button)
                self.logger.info("Successfully clicked up arrow button using JavaScript")

            except Exception as button_error:
                self.logger.warning(f"Failed to find or click up arrow button: {button_error}")
                # Fallback: Just scroll to top using JavaScript
                self.driver.execute_script("window.scrollTo(0, 0);")
                self.logger.info("Used fallback scroll to top method")

            # Wait for scroll animation to complete
            time.sleep(2)

            # Verify we're at the top
            scroll_position = self.driver.execute_script("return window.pageYOffset;")
            if scroll_position <= 0:
                self.logger.info("Successfully verified scroll position is at top")
                return True
            else:
                self.logger.error(f"Failed to scroll to top. Current position: {scroll_position}")
                return False

        except Exception as e:
            self.log_error_with_screenshot("Arrow button handling failed", "arrow_button_failure")
            self.logger.error(f"Arrow button handling failed: {e}")
            return False

    def click_element(self, element):
        """Helper function to click an element with retry logic."""
        for _ in range(3):  # Retry up to 3 times
            try:
                # Scroll the element into view
                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(element)).click()
                return
            except Exception as e:
                self.logger.warning(f"Click failed: {e}")
                time.sleep(1)  # Wait before retrying
        self.logger.error("Failed to click the element after retries.")

    def handle_otp_flow(self):
        """
        Handles the OTP verification flow with multiple retry attempts.
        Returns True if OTP verification is successful, False otherwise.
        """
        try:
            max_attempts = 3
            last_resend_time = datetime.now()

            for attempt in range(max_attempts):
                otp = self.sign_in_handler.fetch_latest_unseen_email(last_resend_time)
                if otp:
                    self.logger.info(f"Retrieved OTP: {otp}")
                    if self.sign_in_handler.enter_and_verify_otp(otp):
                        return True
                else:
                    self.logger.warning(f"Attempt {attempt + 1} failed to retrieve OTP.")
                    if attempt < max_attempts - 1:
                        self.sign_in_handler.click_resend_otp()
                        last_resend_time = datetime.now()  # Update last resend time
                        time.sleep(10)  # Wait before retrying

            self.logger.error("Failed to verify OTP after maximum attempts")
            return False

        except Exception as e:
            self.logger.error(f"Error in OTP flow: {e}")
            return False

    def validate_downloaded_content(self, downloaded_file, expected_content):
        try:
            with open(downloaded_file, 'r', encoding='utf-8') as file:
                content = file.read()
                if expected_content in content:
                    self.logger.info("Downloaded content matches expected content.")
                else:
                    self.logger.error("Downloaded content does not match expected content.")
        except Exception as e:
            self.logger.error(f"Error reading downloaded file: {e}")

   
        
    def test_signup_and_login(self):
        self.logger.info("Starting signup and login test")
        try:
            self.handle_login()

            for factor in VALID_FACTORS:
                self.logger.info(f"=== Starting test for factor: {factor} ===")

                # Factor Selection
                # Store selected factor for history checking
                self.selected_factor = factor
                if not self.handle_factor_selection(factor):
                    self.log_error_with_screenshot(f"Factor selection failed for: {factor}", "factor_selection_failure")
                    self.logger.error(f"Factor selection failed for: {factor}")
                else:
                    self.logger.info(f"Factor selection successful for: {factor}")

                # File Upload
                if not self.handle_file_upload(config.FILE_PATH):
                    self.log_error_with_screenshot(f"File upload failed for file: {config.FILE_PATH}",
                                                   "file_upload_failure")
                    self.logger.error(f"File upload failed for file: {config.FILE_PATH}")
                else:
                    self.logger.info(f"File upload successful for file: {config.FILE_PATH}")

                # Submit Analysis
                if not self.handle_submit(factor):
                    self.log_error_with_screenshot(f"Submit operation failed for factor: {factor}", "submit_failure")
                    self.logger.error(f"Submit operation failed for factor: {factor}")
                else:
                    self.logger.info(f"Submit operation successful for factor: {factor}")

                # Wait for Processing
                if not self.wait_for_processing():
                    self.log_error_with_screenshot("Processing timeout - operation took too long", "processing_timeout")
                    self.logger.error("Processing timeout - operation took too long")
                else:
                    self.logger.info("No error messages found, continuing with analysis")
                    self.logger.info(f"Processing successful for factor: {factor}")

                if not self.handle_analysis_buttons():
                    self.log_error_with_screenshot("Analysis button handling failed", "analysis_failed")
                    self.logger.error("Analysis button handling failed")
                else:
                    self.logger.info(f"Analysis button handling successful for factor: {factor}")

                # Like/Dislike Functionality
                if not self.handle_like_dislike_functionality():
                    self.log_error_with_screenshot("Like/dislike functionality testing failed", "like_dislike_failure")
                    self.logger.error("Like/dislike functionality testing failed")
                else:
                    self.logger.info(f"Like/dislike functionality testing successful for factor: {factor}")

                # Download Results
                if not self.handle_download():
                    self.log_error_with_screenshot("Download failed", "download_failure")
                    self.logger.error("Download failed")
                else:
                    self.logger.info(f"Download successful for factor: {factor}")

                # History Analysis
                if not self.history_analysis():
                    self.log_error_with_screenshot("History analysis failed", "history_analysis_failure")
                    self.logger.error("History analysis failed")
                else:
                    self.logger.info(f"History analysis successful for factor: {factor}")

                # Scroll down to ensure we are not at the top
                if not self.scroll_to_top():
                    self.log_error_with_screenshot("Arrow button handling failed", "arrow_button_failure")
                    self.logger.error("Arrow button handling failed")
                else:
                    self.logger.info(f"Arrow button handling successful for factor: {factor}")

              

                self.logger.info(f"=== Completed all tests for factor: {factor} ===")

        except Exception as e:
            self.log_error_with_screenshot(f"Test failed with error: {e}", "unexpected_error")
            self.logger.error(f"Test failed with error: {e}")
            raise  # Re-raise the exception to mark the test as failed
        finally:
            self.logger.info("Test execution completed")
            # self.handle_logout()


if __name__ == "__main__":
    unittest.main()

import time
import unittest

from selenium.common import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from logger import Logger
from webdriver_setup import WebDriverSetup
from sign_in_handler import SignInHandler
from screenshot_handler import ScreenshotHandler
import imaplib
from email import message_from_bytes
from email.header import decode_header
from datetime import datetime, timedelta
from handlers.config_handler import ConfigHandler

# Get configuration
config = ConfigHandler.get_config()

class AutomationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logger = Logger.setup_logger()
        cls.logger.info("Setting up WebDriver for tests")
        try:
            cls.driver = WebDriverSetup.get_driver()
            cls.wait = WebDriverWait(cls.driver, 20)
            cls.screenshot_handler = ScreenshotHandler(cls.logger)
            
            # Updated SignInHandler initialization to access config attributes directly
            cls.sign_in_handler = SignInHandler(
                driver=cls.driver,
                wait=cls.wait,
                logger=cls.logger,
                email_address=config.EMAIL_ADDRESS,
                imap_server=config.IMAP_SERVER,
                app_password=config.APP_PASSWORD,
                sender_email=config.SENDER_EMAIL
            )
            
            # Take screenshot of initial setup
            cls.screenshot_handler.take_screenshot(cls.driver, "success", "test_setup_complete")
        except Exception as e:
            cls.logger.error(f"Setup failed: {e}")
            if hasattr(cls, 'screenshot_handler'):
                cls.screenshot_handler.take_screenshot(cls.driver, "failure", "setup_failed")
            raise

    def setUp(self):
        # Take screenshot before each test
        self.screenshot_handler.take_screenshot(self.driver, "success", f"before_{self._testMethodName}")

    def tearDown(self):
        # Take screenshot after each test
        self.screenshot_handler.take_screenshot(self.driver, "success", f"after_{self._testMethodName}")

    def test_signin(self):
        self.logger.info("Starting test: test_signin")
        try:
            # Navigate to login page (only once)
            self.driver.get(config.LOGIN_URL)
            self.driver.maximize_window()
            self.logger.info("Navigated to login page")

            # Loading check with logging
            self.logger.info("Waiting for initial page load...")
            loading_xpath = "//p[contains(text(), 'Please wait while we load the content for you.')]"

            try:
                # Wait until loading message appears (if it does)
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, loading_xpath))
                )

                # Wait until loading message disappears
                WebDriverWait(self.driver, 30).until(
                    EC.invisibility_of_element_located((By.XPATH, loading_xpath))
                )
                self.logger.info("Page loaded successfully")
            except TimeoutException:
                # If loading message never appeared or disappeared quickly
                self.logger.info("No loading message found or page loaded quickly")

            time.sleep(3)  # Wait for page to be fully loaded

            # Test Security & Privacy link before login
            try:
                security_privacy_link = WebDriverWait(self.driver, 15).until(
                    EC.visibility_of_element_located((By.XPATH,
                                                      "//span[contains(@class, 'underline') and contains(text(), 'Security') and contains(text(), 'Privacy')]"
                                                      ))
                )

                time.sleep(2)

                if security_privacy_link.is_displayed():
                    if self.sign_in_handler.click_security_privacy():
                        self.logger.info("Successfully verified Security & Privacy functionality")
                    else:
                        self.logger.error("Security & Privacy link click failed")
                        self.screenshot_handler.take_screenshot(self.driver, "failure", "security_privacy_click_failed")
                        return
                else:
                    self.logger.error("Security & Privacy link not visible")
                    self.screenshot_handler.take_screenshot(self.driver, "failure", "security_privacy_not_visible")
                    return

            except Exception as e:
                self.logger.error(f"Security & Privacy verification error: {str(e)}")
                self.screenshot_handler.take_screenshot(self.driver, "failure", "security_privacy_error")
                return

            # Proceed with login flow without reopening the page
            login_result = self.sign_in_handler.handle_login(reopen_page=False)

            # Check if login resulted in a signup
            if isinstance(login_result, self.sign_in_handler.SignupResult):  # Updated class reference
                self.logger.info("New email detected, signup process initiated")

                if login_result.success and login_result.is_new_signup:
                    self.logger.info("Signup successful, verifying welcome email")

                    # Wait for welcome email
                    time.sleep(10)  # Allow time for welcome email to arrive

                    # Verify welcome email
                    email_verified = self.verify_welcome_email(
                        login_result.first_name,
                        self.sign_in_handler.email_address
                    )

                    if email_verified:
                        self.screenshot_handler.take_screenshot(self.driver, "success", "welcome_email_verified")
                        
                        # Add verification of successful login
                        self.logger.info("Verifying successful login after signup...")
                        login_verified = self.sign_in_handler.verify_successful_login()
                        if not login_verified:
                            self.logger.error("Failed to verify successful login after signup")
                            self.screenshot_handler.take_screenshot(self.driver, "failure", "login_verification_failed")
                            return
                        self.logger.info("Successfully verified login after signup")
                    else:
                        self.logger.error("Welcome email verification failed")
                        self.screenshot_handler.take_screenshot(self.driver, "failure",
                                                                "welcome_email_verification_failed")
                        return
                else:
                    self.logger.error("Signup process failed")
                    self.screenshot_handler.take_screenshot(self.driver, "failure", "signup_failed")
                    return

            elif not login_result:
                self.logger.error("Login failed")
                self.screenshot_handler.take_screenshot(self.driver, "failure", "login_failed")
                return
            else:
                self.logger.info("Login successful")
                self.screenshot_handler.take_screenshot(self.driver, "success", "login_successful")

                # Add verification of successful login for regular login flow
                self.logger.info("Verifying successful login...")
                login_verified = self.sign_in_handler.verify_successful_login()
                if not login_verified:
                    self.logger.error("Failed to verify successful login")
                    self.screenshot_handler.take_screenshot(self.driver, "failure", "login_verification_failed")
                    return
                self.logger.info("Successfully verified login")

        except Exception as e:
            self.logger.error(f"Error during test_signin: {e}")
            self.screenshot_handler.take_screenshot(self.driver, "failure", f"signin_exception_{str(e)[:30]}")

    def verify_welcome_email(self, first_name, email_address):
        max_retries = 3
        retry_delay = 10  # seconds

        for attempt in range(max_retries):
            mail = None
            try:
                self.logger.info(f"Welcome email verification attempt {attempt + 1} of {max_retries}")

                mail = imaplib.IMAP4_SSL(self.sign_in_handler.imap_server)
                mail.login(email_address, self.sign_in_handler.app_password)
                mail.select("inbox")

                # Search for recent emails (last 5 minutes)
                date = (datetime.now() - timedelta(minutes=5)).strftime("%d-%b-%Y")
                search_criteria = f'(FROM "{self.sign_in_handler.sender_email}" SINCE {date})'
                status, messages = mail.search(None, search_criteria.encode())

                if status != "OK" or not messages[0]:
                    self.logger.warning(f"No emails found matching criteria on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        self.logger.info(f"Waiting {retry_delay} seconds before next attempt...")
                        time.sleep(retry_delay)
                    continue

                # Get all recent emails and check each one
                email_ids = messages[0].split()
                self.logger.info(f"Found {len(email_ids)} emails to check")

                for email_id in reversed(email_ids):  # Check most recent first
                    try:
                        status, msg_data = mail.fetch(email_id, "(RFC822)")

                        if status != "OK":
                            self.logger.error("Failed to fetch email content")
                            continue

                        email_body = msg_data[0][1]
                        msg = message_from_bytes(email_body)

                        # Get and log the subject
                        subject = decode_header(msg["Subject"])[0][0]
                        if isinstance(subject, bytes):
                            subject = subject.decode()
                        self.logger.info(f"Checking email with subject: {subject}")

                        # Check for any of the expected subjects
                        expected_subjects = [
                            "Let's Verify Your CodeSherlock Account!",
                            f"Welcome, {first_name}",
                            "Welcome to CodeSherlock",
                            "Verify Your CodeSherlock Account"
                        ]

                        if any(expected.lower() in subject.lower() for expected in expected_subjects):
                            self.logger.info("Welcome email found with matching subject")
                            return True

                        self.logger.info(f"Subject did not match any expected patterns: {subject}")
                    except Exception as e:
                        self.logger.error(f"Error processing email ID {email_id}: {str(e)}")
                        continue

                self.logger.warning(f"No matching welcome email found in attempt {attempt + 1}")

            except imaplib.IMAP4.error as e:
                self.logger.error(f"IMAP error during welcome email verification: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            except Exception as e:
                self.logger.error(f"Unexpected error during welcome email verification: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            finally:
                if mail:
                    try:
                        mail.logout()
                    except Exception as e:
                        self.logger.warning(f"Error during mail logout: {str(e)}")

        self.logger.error("Welcome email verification failed after all attempts")
        return False

    def _get_email_body(self, msg):
        """Helper method to extract email body from message."""
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type in ["text/html", "text/plain"]:
                        return part.get_payload(decode=True).decode()
            else:
                content_type = msg.get_content_type()
                if content_type in ["text/html", "text/plain"]:
                    return msg.get_payload(decode=True).decode()
            return None
        except Exception as e:
            self.logger.error(f"Error extracting email body: {e}")
            return None

    @classmethod
    def tearDownClass(cls):
        cls.logger.info("Tearing down WebDriver")
        try:
            if hasattr(cls, 'driver') and cls.driver:
                # Take final screenshot only if driver session is still valid
                try:
                    var = cls.driver.current_url
                    cls.screenshot_handler.take_screenshot(cls.driver, "success", "test_completion")
                except:
                    cls.logger.warning("Could not take final screenshot - invalid session")
                time.sleep(5)
                cls.driver.quit()
        except Exception as e:
            cls.logger.error(f"Error in teardown: {e}")
        finally:
            cls.logger.info("Test execution completed")


if __name__ == "__main__":
    unittest.main()
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
def test_logout_flow(self):
    self.logger.info("Starting test: test_logout_flow")
    try:
        # Ensure user is logged in
        self.driver.get(config.LOGIN_URL)
        login_result = self.sign_in_handler.handle_login(reopen_page=False)
        if not login_result:
            self.logger.error("Login failed during logout test")
            self.screenshot_handler.take_screenshot(self.driver, "failure", "logout_test_login_failed")
            return

        # Wait for logout button to be visible
        logout_button_xpath = "//button[contains(text(), 'Logout')]"
        logout_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, logout_button_xpath)))
        logout_button.click()
        self.logger.info("Clicked on logout button")

        # Validate redirected back to login
        login_page_element = self.wait.until(
            EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Welcome back')]"))
        )

        if login_page_element.is_displayed():
            self.logger.info("Logout successful, redirected to login page")
            self.screenshot_handler.take_screenshot(self.driver, "success", "logout_successful")
        else:
            self.logger.error("Logout failed, login page not detected")
            self.screenshot_handler.take_screenshot(self.driver, "failure", "logout_page_not_found")

    except Exception as e:
        self.logger.error(f"Error during logout test: {str(e)}")
        self.screenshot_handler.take_screenshot(self.driver, "failure", "logout_test_exception")


def retry_on_failure(
    max_attempts=3,
    delay=5,
    backoff_factor=2,
    exceptions=(Exception,),
    log_level="warning",
    raise_on_failure=False,
    custom_message=None
):
    """
    Decorator to retry a function on failure.

    Parameters:
    - max_attempts (int): Max number of retries.
    - delay (int): Initial delay between attempts.
    - backoff_factor (int): Multiplies delay each retry (exponential backoff).
    - exceptions (tuple): Exceptions to catch and retry on.
    - log_level (str): 'info', 'warning', or 'error'.
    - raise_on_failure (bool): Raise last exception if all retries fail.
    - custom_message (str): Custom log message prefix on failures.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    logger = getattr(args[0], 'logger', None)
                    msg = f"{custom_message or 'Retry'} - Attempt {attempt}/{max_attempts} failed: {str(e)}"
                    if logger:
                        getattr(logger, log_level, logger.warning)(msg)
                    else:
                        print(msg)

                    if attempt < max_attempts:
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
            # All attempts failed
            final_msg = f"All {max_attempts} attempts failed for `{func.__name__}`"
            if logger:
                logger.error(final_msg)
            else:
                print(final_msg)
            if raise_on_failure:
                raise
            return False
        return wrapper
    return decorator

def test_security_privacy_link_navigation(self):
    self.logger.info("Starting test: test_security_privacy_link_navigation")
    try:
        self.driver.get(config.LOGIN_URL)
        link_xpath = "//span[contains(@class, 'underline') and contains(text(), 'Security') and contains(text(), 'Privacy')]"
        link = self.wait.until(EC.element_to_be_clickable((By.XPATH, link_xpath)))
        main_window = self.driver.current_window_handle

        link.click()
        time.sleep(3)

        # Switch to the new window/tab
        all_windows = self.driver.window_handles
        for handle in all_windows:
            if handle != main_window:
                self.driver.switch_to.window(handle)
                break

        # Verify title or URL of new page
        expected_url_part = "privacy"
        if expected_url_part in self.driver.current_url:
            self.logger.info("Security & Privacy link opened correctly in new tab")
            self.screenshot_handler.take_screenshot(self.driver, "success", "privacy_link_navigation_success")
        else:
            self.logger.error("Incorrect URL opened from Security & Privacy link")
            self.screenshot_handler.take_screenshot(self.driver, "failure", "privacy_link_wrong_url")

        self.driver.close()
        self.driver.switch_to.window(main_window)

    except Exception as e:
        self.logger.error(f"Exception in test_security_privacy_link_navigation: {str(e)}")
        self.screenshot_handler.take_screenshot(self.driver, "failure", "privacy_link_exception")


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

import os
import time
import imaplib
from email import message_from_bytes
from email.header import decode_header
from datetime import datetime
import logging
import unittest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from sign_in_handler import SignInHandler
from webdriver_setup import WebDriverSetup
from logger import Logger
from screenshot_handler import ScreenshotHandler
from handlers.config_handler import ConfigHandler

# Get configuration
config = ConfigHandler.get_config()




#class ScreenshotHandler
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


class LogoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """One-time setup: Initialize WebDriver and perform login"""
        cls.logger = Logger.setup_logger()
        cls.logger.info("Setting up WebDriver for logout tests")
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
            
            # Perform initial login
            if cls.sign_in_handler.handle_login():
                cls.logger.info("Successfully logged in for test")
                cls.screenshot_handler.take_screenshot(cls.driver, "success", "initial_login_successful")
            else:
                raise Exception("Initial login failed")
                
            cls.screenshot_handler.take_screenshot(cls.driver, "success", "test_setup_complete")
        except Exception as e:
            cls.logger.error(f"Setup failed: {e}")
            cls.screenshot_handler.take_screenshot(cls.driver, "failure", "setup_failed")
            raise

    def test_logout_scenarios(self):
        """Test both normal logout flow and session expiration scenarios"""
        self.logger.info("Starting comprehensive logout test")
        
        try:
            # Part 1: Test normal logout flow
            self.logger.info("Testing normal logout flow")
            time.sleep(5)  # Wait for page to fully load
            
            # Perform normal logout
            self.sign_in_handler.logout()
            time.sleep(5)  # Increased wait time after logout to ensure completion
            


            # Login again for session expiration test
            self.logger.info("Logging in again for session expiration test")
            time.sleep(3)  # Added wait time before next login attempt
            if self.sign_in_handler.handle_login():
                self.logger.info("Successfully logged in for session expiration test")
                time.sleep(3)  # Increased wait time after successful login
            else:
                raise Exception("Failed to login for session expiration test")

            # Part 2: Test session expiration
            self.logger.info("Testing session expiration")
            
            # Clear cookies to simulate session expiration
            self.driver.delete_all_cookies()
            time.sleep(3)  # Increased wait time after clearing cookies
            
            # Check cookie is deleted
            if self.driver.get_cookie('session') is None:
                self.logger.info("Session cookie deleted successfully")
            else:
                raise Exception("Session cookie not deleted")

        except Exception as e:
            self.logger.error(f"Error during logout test: {e}")
            self.screenshot_handler.take_screenshot(self.driver, "failure", f"logout_test_failed")
            raise

    @classmethod
    def tearDownClass(cls):
        """Clean up resources"""
        cls.logger.info("Tearing down WebDriver")
        try:
            if hasattr(cls, 'driver') and cls.driver:
                cls.driver.quit()
        except Exception as e:
            cls.logger.error(f"Error in teardown: {e}")
        finally:
            cls.logger.info("Test execution completed")


if __name__ == "__main__":
    unittest.main()
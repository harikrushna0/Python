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

            time.sleep(5) 
            # added before logout to allow page to fully load
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
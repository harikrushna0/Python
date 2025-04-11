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
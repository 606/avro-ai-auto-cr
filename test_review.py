#!/usr/bin/env python3
"""
Test file for AI code review
This file has some potential issues to trigger the review system.
"""

import os
import hashlib

def process_user_data(user_input, password):
    """Process user data - has security issues"""
    # Security issue: using MD5 for password hashing
    hashed_password = hashlib.md5(password.encode()).hexdigest()

    # Security issue: SQL injection vulnerability
    query = f"SELECT * FROM users WHERE name = '{user_input}'"

    # Performance issue: inefficient string concatenation
    result = ""
    for i in range(1000):
        result += f"Item {i} "

    return query, hashed_password, result

def async_function():
    """Async function without proper error handling"""
    # Missing try-catch for async operations
    data = fetch_data_from_api()
    return data

# Memory issue: not using context manager
file = open('test.txt', 'w')
file.write('test data')
# Missing file.close()

if __name__ == "__main__":
    user_data = input("Enter your data: ")
    pwd = input("Enter password: ")
    result = process_user_data(user_data, pwd)
    print(result)

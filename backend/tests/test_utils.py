def validate_property(test_case, property_data, expected_source=None):
    """
    Validates a single property dictionary.
    
    Args:
        test_case: The unittest.TestCase instance (to use assert methods).
        property_data: The dictionary containing property details.
        expected_source: (Optional) The expected source string.
    """
    test_case.assertIsNotNone(property_data, "Property data should not be None")
    
    # Check for required fields
    required_fields = ["code", "price", "location", "source", "link", "title"]
    for field in required_fields:
        test_case.assertIn(field, property_data, f"Property missing required field: {field}")
        
    # Check values are not empty strings (where critical)
    test_case.assertTrue(property_data["code"], "Property code should not be empty")
    test_case.assertTrue(property_data["price"], "Property price should not be empty")
    test_case.assertTrue(property_data["link"], "Property link should not be empty")
    
    if expected_source:
        test_case.assertEqual(property_data["source"], expected_source, f"Source should be {expected_source}")

    # Optional: Log success for debugging if needed (or just rely on test passing)
    # print(f"Validated property {property_data['code']} from {property_data['source']}")

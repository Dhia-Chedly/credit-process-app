# Reference data

Reference administrators manage agencies, agency codes, CA/CAA and GP employees, credit types, activities, request types, and rejection reasons in the **Reference Data** page. Other operators can view and import data but cannot change these values.

Deactivate an obsolete value instead of deleting it. Deactivation blocks new imports that use the value while preserving published requests and historical analytics. Reactivation allows future imports to use it again.

Agency codes are unique four-digit numbers and form the first segment of each request reference. Changing a code does not rewrite existing references; new imports must use the current code.

A CA/CAA or GP belongs to one agency. Imports match their names without case or accent differences, but require a unique active employee in the worksheet's agency. Update the employee's agency when they transfer. A work email is optional for imports and required only for email alerts.

Add or reactivate controlled values before retrying a rejected workbook. Unknown, inactive, or ambiguous values block import; the system does not substitute a generic value.

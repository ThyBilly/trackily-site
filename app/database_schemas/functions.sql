-- ============================================================================
-- StockWatch Production Utility Functions
-- ============================================================================

-- Use the stockwatch database
USE stockwatch;

-- Change delimiter to allow semicolons in function bodies
DELIMITER //

-- ============================================================================
-- Function: is_valid_email
-- Description: Validates email format using basic regex
-- Parameters: 
--   email_address: Email to validate
-- Returns: BOOLEAN (TRUE if valid, FALSE if invalid)
-- ============================================================================
DROP FUNCTION IF EXISTS is_valid_email//

CREATE FUNCTION is_valid_email(email_address VARCHAR(255))
RETURNS BOOLEAN
READS SQL DATA
DETERMINISTIC
BEGIN
    DECLARE is_valid BOOLEAN DEFAULT FALSE;
    
    -- Basic email validation regex
    IF email_address IS NOT NULL 
       AND email_address REGEXP '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
       AND CHAR_LENGTH(email_address) <= 255
       AND CHAR_LENGTH(email_address) >= 6 THEN
        SET is_valid = TRUE;
    END IF;
    
    RETURN is_valid;
END//

-- ============================================================================
-- Function: get_user_display_name
-- Description: Gets the display name for a user (full name or email)
-- Parameters: 
--   user_id: User's ID
-- Returns: VARCHAR(255) - Display name
-- ============================================================================
DROP FUNCTION IF EXISTS get_user_display_name//

CREATE FUNCTION get_user_display_name(user_id INT)
RETURNS VARCHAR(255)
READS SQL DATA
DETERMINISTIC
BEGIN
    DECLARE display_name VARCHAR(255) DEFAULT '';
    DECLARE user_full_name VARCHAR(255) DEFAULT '';
    DECLARE user_email VARCHAR(255) DEFAULT '';
    
    -- Get user details
    SELECT full_name, email INTO user_full_name, user_email
    FROM users 
    WHERE id = user_id AND is_active = TRUE
    LIMIT 1;
    
    -- Use full name if available, otherwise use email
    IF user_full_name IS NOT NULL AND TRIM(user_full_name) != '' THEN
        SET display_name = user_full_name;
    ELSEIF user_email IS NOT NULL THEN
        SET display_name = user_email;
    ELSE
        SET display_name = CONCAT('User #', user_id);
    END IF;
    
    RETURN display_name;
END//

-- ============================================================================
-- Function: calculate_password_strength
-- Description: Calculates password strength score (0-5)
-- Parameters: 
--   password_text: Password to analyze
-- Returns: INT - Strength score (0-5)
-- ============================================================================
DROP FUNCTION IF EXISTS calculate_password_strength//

CREATE FUNCTION calculate_password_strength(password_text TEXT)
RETURNS INT
DETERMINISTIC
NO SQL
BEGIN
    DECLARE strength_score INT DEFAULT 0;
    
    IF password_text IS NULL THEN
        RETURN 0;
    END IF;
    
    -- Length check (8+ characters)
    IF CHAR_LENGTH(password_text) >= 8 THEN
        SET strength_score = strength_score + 1;
    END IF;
    
    -- Contains lowercase letter
    IF password_text REGEXP '[a-z]' THEN
        SET strength_score = strength_score + 1;
    END IF;
    
    -- Contains uppercase letter
    IF password_text REGEXP '[A-Z]' THEN
        SET strength_score = strength_score + 1;
    END IF;
    
    -- Contains number
    IF password_text REGEXP '[0-9]' THEN
        SET strength_score = strength_score + 1;
    END IF;
    
    -- Contains special character
    IF password_text REGEXP '[^a-zA-Z0-9]' THEN
        SET strength_score = strength_score + 1;
    END IF;
    
    RETURN strength_score;
END//

-- ============================================================================
-- Function: get_days_since_registration
-- Description: Gets number of days since user registration
-- Parameters: 
--   user_id: User's ID
-- Returns: INT - Days since registration
-- ============================================================================
DROP FUNCTION IF EXISTS get_days_since_registration//

CREATE FUNCTION get_days_since_registration(user_id INT)
RETURNS INT
READS SQL DATA
DETERMINISTIC
BEGIN
    DECLARE days_since INT DEFAULT 0;
    DECLARE reg_date TIMESTAMP;
    
    -- Get registration date
    SELECT created_at INTO reg_date
    FROM users 
    WHERE id = user_id
    LIMIT 1;
    
    IF reg_date IS NOT NULL THEN
        SET days_since = DATEDIFF(NOW(), reg_date);
    END IF;
    
    RETURN days_since;
END//

-- ============================================================================
-- Function: get_user_login_streak
-- Description: Gets user's current login streak in days
-- Parameters: 
--   user_id: User's ID
-- Returns: INT - Current login streak
-- ============================================================================
DROP FUNCTION IF EXISTS get_user_login_streak//

CREATE FUNCTION get_user_login_streak(user_id INT)
RETURNS INT
READS SQL DATA
DETERMINISTIC
BEGIN
    DECLARE login_streak INT DEFAULT 0;
    DECLARE last_login TIMESTAMP;
    
    -- Get last login date
    SELECT last_login_at INTO last_login
    FROM users 
    WHERE id = user_id
    LIMIT 1;
    
    IF last_login IS NOT NULL THEN
        -- Simple streak calculation - days since last login
        -- (In a real application, you'd want a more sophisticated streak calculation
        --  that tracks consecutive days with logins)
        SET login_streak = GREATEST(0, 7 - DATEDIFF(NOW(), last_login));
    END IF;
    
    RETURN login_streak;
END//

-- ============================================================================
-- Function: generate_display_initials
-- Description: Generates user initials from full name
-- Parameters: 
--   full_name: User's full name
-- Returns: VARCHAR(5) - User initials (max 2-3 characters)
-- ============================================================================
DROP FUNCTION IF EXISTS generate_display_initials//

CREATE FUNCTION generate_display_initials(full_name VARCHAR(255))
RETURNS VARCHAR(5)
DETERMINISTIC
NO SQL
BEGIN
    DECLARE initials VARCHAR(5) DEFAULT '';
    DECLARE first_char VARCHAR(1) DEFAULT '';
    DECLARE space_pos INT DEFAULT 0;
    DECLARE second_char VARCHAR(1) DEFAULT '';
    
    IF full_name IS NULL OR TRIM(full_name) = '' THEN
        RETURN '??';
    END IF;
    
    -- Get first character
    SET first_char = UPPER(LEFT(TRIM(full_name), 1));
    
    -- Find first space to get second initial
    SET space_pos = LOCATE(' ', TRIM(full_name));
    
    IF space_pos > 0 AND space_pos < CHAR_LENGTH(TRIM(full_name)) THEN
        -- Get first character after the space
        SET second_char = UPPER(SUBSTRING(TRIM(full_name), space_pos + 1, 1));
        SET initials = CONCAT(first_char, second_char);
    ELSE
        -- No space found, just use first character
        SET initials = first_char;
    END IF;
    
    RETURN initials;
END//

-- ============================================================================
-- Function: format_user_join_date
-- Description: Formats user join date in a friendly format
-- Parameters: 
--   user_id: User's ID
-- Returns: VARCHAR(50) - Formatted join date
-- ============================================================================
DROP FUNCTION IF EXISTS format_user_join_date//

CREATE FUNCTION format_user_join_date(user_id INT)
RETURNS VARCHAR(50)
READS SQL DATA
DETERMINISTIC
BEGIN
    DECLARE join_date_formatted VARCHAR(50) DEFAULT '';
    DECLARE reg_date TIMESTAMP;
    
    -- Get registration date
    SELECT created_at INTO reg_date
    FROM users 
    WHERE id = user_id
    LIMIT 1;
    
    IF reg_date IS NOT NULL THEN
        SET join_date_formatted = DATE_FORMAT(reg_date, 'Joined %M %Y');
    ELSE
        SET join_date_formatted = 'Join date unknown';
    END IF;
    
    RETURN join_date_formatted;
END//

-- ============================================================================
-- Function: get_subscription_plan_type
-- Description: Gets the current subscription plan type for a user
-- Parameters: 
--   user_id: User's ID
-- Returns: VARCHAR(50) - Plan type (free, pay_as_you_go, unlimited)
-- ============================================================================
DROP FUNCTION IF EXISTS get_subscription_plan_type//

CREATE FUNCTION get_subscription_plan_type(user_id INT)
RETURNS VARCHAR(50)
READS SQL DATA
DETERMINISTIC
BEGIN
    DECLARE plan_type VARCHAR(50) DEFAULT 'free';
    
    -- Get user's current plan type
    SELECT sp.plan_type INTO plan_type
    FROM user_subscriptions us
    JOIN subscription_plans sp ON us.plan_id = sp.id
    WHERE us.user_id = user_id AND us.status = 'active'
    LIMIT 1;
    
    -- If no active subscription found, default to free
    IF plan_type IS NULL THEN
        SET plan_type = 'free';
    END IF;
    
    RETURN plan_type;
END//

-- ============================================================================
-- Function: get_user_product_limit
-- Description: Gets the product limit for a user based on their subscription
-- Parameters: 
--   user_id: User's ID
-- Returns: INT - Product limit (-1 for unlimited)
-- ============================================================================
DROP FUNCTION IF EXISTS get_user_product_limit//

CREATE FUNCTION get_user_product_limit(user_id INT)
RETURNS INT
READS SQL DATA
DETERMINISTIC
BEGIN
    DECLARE product_limit INT DEFAULT 2;
    DECLARE plan_type VARCHAR(50) DEFAULT 'free';
    
    -- Get user's subscription details
    SELECT 
        sp.plan_type,
        COALESCE(us.custom_product_limit, sp.max_products) as max_products
    INTO plan_type, product_limit
    FROM user_subscriptions us
    JOIN subscription_plans sp ON us.plan_id = sp.id
    WHERE us.user_id = user_id AND us.status = 'active'
    LIMIT 1;
    
    -- Handle unlimited plans
    IF plan_type = 'unlimited' OR product_limit IS NULL THEN
        SET product_limit = -1; -- -1 indicates unlimited
    END IF;
    
    -- Default to free plan if no subscription found
    IF product_limit IS NULL THEN
        SET product_limit = 2;
    END IF;
    
    RETURN product_limit;
END//

-- ============================================================================
-- Function: extract_store_name_from_url
-- Description: Extracts store name from a product URL
-- Parameters: 
--   product_url: Product URL
-- Returns: VARCHAR(100) - Store name
-- ============================================================================
DROP FUNCTION IF EXISTS extract_store_name_from_url//

CREATE FUNCTION extract_store_name_from_url(product_url VARCHAR(1000))
RETURNS VARCHAR(100)
DETERMINISTIC
NO SQL
BEGIN
    DECLARE store_name VARCHAR(100) DEFAULT 'Other';
    
    IF product_url IS NULL OR TRIM(product_url) = '' THEN
        RETURN 'Unknown';
    END IF;
    
    -- Convert to lowercase for matching
    SET product_url = LOWER(product_url);
    
    -- Extract store name based on URL patterns
    IF product_url LIKE '%amazon.%' THEN
        SET store_name = 'Amazon';
    ELSEIF product_url LIKE '%ebay.%' THEN
        SET store_name = 'eBay';
    ELSEIF product_url LIKE '%bestbuy.%' THEN
        SET store_name = 'Best Buy';
    ELSEIF product_url LIKE '%target.%' THEN
        SET store_name = 'Target';
    ELSEIF product_url LIKE '%walmart.%' THEN
        SET store_name = 'Walmart';
    ELSEIF product_url LIKE '%newegg.%' THEN
        SET store_name = 'Newegg';
    ELSEIF product_url LIKE '%costco.%' THEN
        SET store_name = 'Costco';
    ELSEIF product_url LIKE '%homedepot.%' THEN
        SET store_name = 'Home Depot';
    ELSEIF product_url LIKE '%lowes.%' THEN
        SET store_name = 'Lowes';
    ELSEIF product_url LIKE '%etsy.%' THEN
        SET store_name = 'Etsy';
    ELSE
        SET store_name = 'Other';
    END IF;
    
    RETURN store_name;
END//

-- ============================================================================
-- Function: calculate_savings_potential
-- Description: Calculates potential savings for a product based on price history
-- Parameters: 
--   product_id: Product ID
-- Returns: DECIMAL(10,2) - Potential savings amount
-- ============================================================================
DROP FUNCTION IF EXISTS calculate_savings_potential//

CREATE FUNCTION calculate_savings_potential(product_id INT)
RETURNS DECIMAL(10,2)
READS SQL DATA
DETERMINISTIC
BEGIN
    DECLARE current_price DECIMAL(10,2) DEFAULT 0.00;
    DECLARE lowest_price DECIMAL(10,2) DEFAULT 0.00;
    DECLARE highest_price DECIMAL(10,2) DEFAULT 0.00;
    DECLARE savings DECIMAL(10,2) DEFAULT 0.00;
    
    -- Get current price
    SELECT up.current_price INTO current_price
    FROM user_products up
    WHERE up.id = product_id
    LIMIT 1;
    
    -- Get lowest and highest prices from history
    SELECT 
        MIN(price) as min_price,
        MAX(price) as max_price
    INTO lowest_price, highest_price
    FROM product_price_history
    WHERE product_id = product_id;
    
    -- Calculate savings potential
    IF current_price IS NOT NULL AND highest_price IS NOT NULL THEN
        SET savings = highest_price - current_price;
        IF savings < 0 THEN
            SET savings = 0.00;
        END IF;
    END IF;
    
    RETURN savings;
END//

-- ============================================================================
-- Function: format_price_with_currency
-- Description: Formats a price with currency symbol
-- Parameters: 
--   price: Price amount
--   currency_code: Currency code (USD, EUR, etc.)
-- Returns: VARCHAR(20) - Formatted price string
-- ============================================================================
DROP FUNCTION IF EXISTS format_price_with_currency//

CREATE FUNCTION format_price_with_currency(price DECIMAL(10,2), currency_code VARCHAR(3))
RETURNS VARCHAR(20)
DETERMINISTIC
NO SQL
BEGIN
    DECLARE formatted_price VARCHAR(20) DEFAULT '';
    DECLARE currency_symbol VARCHAR(5) DEFAULT '$';
    
    -- Handle NULL price
    IF price IS NULL THEN
        RETURN 'N/A';
    END IF;
    
    -- Set currency symbol based on code
    IF currency_code = 'EUR' THEN
        SET currency_symbol = '€';
    ELSEIF currency_code = 'GBP' THEN
        SET currency_symbol = '£';
    ELSEIF currency_code = 'JPY' THEN
        SET currency_symbol = '¥';
    ELSEIF currency_code = 'CAD' THEN
        SET currency_symbol = 'C$';
    ELSE
        SET currency_symbol = '$'; -- Default to USD
    END IF;
    
    -- Format the price
    SET formatted_price = CONCAT(currency_symbol, FORMAT(price, 2));
    
    RETURN formatted_price;
END//

-- ============================================================================
-- Function: get_user_timezone
-- Description: Gets user's timezone (placeholder for future implementation)
-- Parameters: 
--   user_id: User's ID
-- Returns: VARCHAR(50) - Timezone string
-- ============================================================================
DROP FUNCTION IF EXISTS get_user_timezone//

CREATE FUNCTION get_user_timezone(user_id INT)
RETURNS VARCHAR(50)
READS SQL DATA
DETERMINISTIC
BEGIN
    -- Placeholder function - in a real implementation, you'd store timezone in user settings
    -- For now, return default timezone
    RETURN 'America/New_York';
END//

-- Reset delimiter
DELIMITER ;

-- ============================================================================
-- Test Queries (Uncomment to test functions)
-- ============================================================================

-- Test email validation
-- SELECT is_valid_email('test@example.com') AS valid_email;
-- SELECT is_valid_email('invalid-email') AS invalid_email;

-- Test display name function
-- SELECT get_user_display_name(1) AS display_name;

-- Test password strength
-- SELECT calculate_password_strength('password123') AS weak_password;
-- SELECT calculate_password_strength('MyStr0ng!P@ssw0rd') AS strong_password;

-- Test initials generation
-- SELECT generate_display_initials('John Doe') AS initials;
-- SELECT generate_display_initials('Madonna') AS single_name;

-- Test days since registration
-- SELECT get_days_since_registration(1) AS days_registered;

-- Test formatted join date
-- SELECT format_user_join_date(1) AS join_date;

-- Test subscription functions
-- SELECT get_subscription_plan_type(1) AS plan_type;
-- SELECT get_user_product_limit(1) AS product_limit;

-- Test store extraction
-- SELECT extract_store_name_from_url('https://www.amazon.com/product') AS store_name;

-- Test price formatting
-- SELECT format_price_with_currency(99.99, 'USD') AS formatted_price;
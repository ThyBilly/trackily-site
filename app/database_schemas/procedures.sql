-- ============================================================================
-- StockWatch Production Stored Procedures with SMS Support - FINALIZED
-- ============================================================================

-- Use the stockwatch database
USE stockwatch;

-- Change delimiter to allow semicolons in procedure bodies
DELIMITER //

-- ============================================================================
-- AUTHENTICATION PROCEDURES
-- ============================================================================

-- ============================================================================
-- Procedure: create_user_account
-- Description: Creates a new user account with validation
-- Used by: auth route - register
-- ============================================================================
DROP PROCEDURE IF EXISTS create_user_account//

CREATE PROCEDURE create_user_account(
    IN p_full_name VARCHAR(255),
    IN p_email VARCHAR(255),
    IN p_password_hash VARCHAR(255),
    IN p_newsletter_opt_in BOOLEAN
)
BEGIN
    DECLARE user_exists INT DEFAULT 0;
    DECLARE new_user_id INT DEFAULT 0;
    DECLARE free_plan_id INT DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT 'error' as status, 'Database error occurred during registration' as message, 0 as user_id;
    END;

    START TRANSACTION;

    -- Validate input parameters
    IF p_full_name IS NULL OR TRIM(p_full_name) = '' THEN
        SELECT 'error' as status, 'Full name is required' as message, 0 as user_id;
        ROLLBACK;
    ELSEIF p_email IS NULL OR TRIM(p_email) = '' THEN
        SELECT 'error' as status, 'Email address is required' as message, 0 as user_id;
        ROLLBACK;
    ELSEIF p_password_hash IS NULL OR TRIM(p_password_hash) = '' THEN
        SELECT 'error' as status, 'Password is required' as message, 0 as user_id;
        ROLLBACK;
    ELSE
        -- Check if email already exists
        SELECT COUNT(*) INTO user_exists 
        FROM users 
        WHERE email = LOWER(TRIM(p_email));

        IF user_exists > 0 THEN
            SELECT 'error' as status, 'An account with this email address already exists' as message, 0 as user_id;
            ROLLBACK;
        ELSE
            -- Insert new user
            INSERT INTO users (
                full_name, 
                email, 
                password_hash, 
                newsletter_opt_in,
                email_verified,
                is_active,
                created_at,
                updated_at
            ) VALUES (
                TRIM(p_full_name),
                LOWER(TRIM(p_email)),
                p_password_hash,
                COALESCE(p_newsletter_opt_in, FALSE),
                FALSE,
                TRUE,
                NOW(),
                NOW()
            );

            SET new_user_id = LAST_INSERT_ID();

            -- Create default settings for new user
            INSERT INTO user_settings (user_id) VALUES (new_user_id);

            -- Try to create default free subscription if a free plan exists
            SELECT id INTO free_plan_id
            FROM subscription_plans
            WHERE plan_type = 'free' AND is_active = TRUE
            LIMIT 1;

            -- Only create subscription if a free plan exists in the database
            IF free_plan_id IS NOT NULL THEN
                INSERT INTO user_subscriptions (user_id, plan_id, status)
                VALUES (new_user_id, free_plan_id, 'active');
            END IF;
            -- If no free plan exists, user will have no subscription (which is handled by the app)

            -- Log the registration activity
            INSERT INTO user_activity_log (user_id, activity_type, success, created_at)
            VALUES (new_user_id, 'register', TRUE, NOW());

            SELECT 'success' as status, 'Account created successfully' as message, 
                   new_user_id as user_id, TRIM(p_full_name) as created_full_name, 
                   LOWER(TRIM(p_email)) as created_email;
            COMMIT;
        END IF;
    END IF;
END//

-- ============================================================================
-- Procedure: verify_user_login
-- Description: Verifies user credentials for login
-- Used by: auth route - login
-- ============================================================================
DROP PROCEDURE IF EXISTS verify_user_login//

CREATE PROCEDURE verify_user_login(
    IN p_email VARCHAR(255)
)
BEGIN
    DECLARE user_count INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SELECT 'error' as status, 'Database error occurred during login verification' as message, 
               0 as user_id, '' as password_hash, '' as full_name, FALSE as email_verified, FALSE as is_active;
    END;

    -- Validate input
    IF p_email IS NULL OR TRIM(p_email) = '' THEN
        SELECT 'error' as status, 'Email address is required' as message,
               0 as user_id, '' as password_hash, '' as full_name, FALSE as email_verified, FALSE as is_active;
    ELSE
        -- Check if user exists
        SELECT COUNT(*) INTO user_count 
        FROM users 
        WHERE email = LOWER(TRIM(p_email));

        IF user_count = 0 THEN
            SELECT 'error' as status, 'Invalid email or password' as message,
                   0 as user_id, '' as password_hash, '' as full_name, FALSE as email_verified, FALSE as is_active;
        ELSE
            -- Return user data for verification
            SELECT 'success' as status, 
                   'User found' as message,
                   id as user_id,
                   password_hash,
                   full_name,
                   email_verified,
                   is_active,
                   email as verified_email
            FROM users 
            WHERE email = LOWER(TRIM(p_email))
            LIMIT 1;
        END IF;
    END IF;
END//

-- ============================================================================
-- Procedure: update_user_last_login
-- Description: Updates the last login timestamp for a user
-- Used by: auth route - login
-- ============================================================================
DROP PROCEDURE IF EXISTS update_user_last_login//

CREATE PROCEDURE update_user_last_login(
    IN p_user_id INT
)
BEGIN
    DECLARE user_exists INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SELECT 'error' as status, 'Database error occurred while updating last login' as message;
    END;

    -- Validate input
    IF p_user_id IS NULL OR p_user_id <= 0 THEN
        SELECT 'error' as status, 'Valid user ID is required' as message;
    ELSE
        -- Check if user exists
        SELECT COUNT(*) INTO user_exists 
        FROM users 
        WHERE id = p_user_id AND is_active = TRUE;

        IF user_exists = 0 THEN
            SELECT 'error' as status, 'User not found or inactive' as message;
        ELSE
            -- Update last login timestamp
            UPDATE users 
            SET last_login_at = NOW(), updated_at = NOW()
            WHERE id = p_user_id;

            -- Log the login activity
            INSERT INTO user_activity_log (user_id, activity_type, success, created_at)
            VALUES (p_user_id, 'login', TRUE, NOW());

            SELECT 'success' as status, 'Last login updated successfully' as message,
                   p_user_id as updated_user_id, NOW() as login_timestamp;
        END IF;
    END IF;
END//

-- ============================================================================
-- Procedure: get_user_by_id
-- Description: Retrieves user information by user ID
-- Used by: auth route - verify-token, refresh
-- ============================================================================
DROP PROCEDURE IF EXISTS get_user_by_id//

CREATE PROCEDURE get_user_by_id(
    IN p_user_id INT
)
BEGIN
    DECLARE user_count INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SELECT 'error' as status, 'Database error occurred while retrieving user' as message,
               '' as email, '' as full_name, FALSE as email_verified;
    END;

    -- Validate input
    IF p_user_id IS NULL OR p_user_id <= 0 THEN
        SELECT 'error' as status, 'Valid user ID is required' as message,
               '' as email, '' as full_name, FALSE as email_verified;
    ELSE
        -- Check if user exists
        SELECT COUNT(*) INTO user_count 
        FROM users 
        WHERE id = p_user_id AND is_active = TRUE;

        IF user_count = 0 THEN
            SELECT 'error' as status, 'User not found or inactive' as message,
                   '' as email, '' as full_name, FALSE as email_verified;
        ELSE
            -- Return user information
            SELECT 'success' as status,
                   'User found' as message,
                   email,
                   full_name,
                   email_verified,
                   p_user_id as queried_user_id,
                   created_at as user_registered_at
            FROM users 
            WHERE id = p_user_id AND is_active = TRUE
            LIMIT 1;
        END IF;
    END IF;
END//

-- ============================================================================
-- PREMIUM SUBSCRIPTION PROCEDURES
-- ============================================================================

-- ============================================================================
-- Procedure: get_user_subscription_info
-- Description: Get user's current subscription details with limits
-- Used by: premium route - get subscription
-- FINALIZED: Column order matches Python expectations
-- ============================================================================
DROP PROCEDURE IF EXISTS get_user_subscription_info//

CREATE PROCEDURE get_user_subscription_info(
    IN p_user_id INT
)
BEGIN
    DECLARE user_exists INT DEFAULT 0;
    DECLARE has_subscription INT DEFAULT 0;
    DECLARE product_count INT DEFAULT 0;
    
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SELECT 'error' as status, 'Database error occurred while retrieving subscription info' as message,
               NULL as subscription_id, 'Free Plan' as plan_name, 'free' as plan_type, 0.00 as price_per_month,
               NULL as price_per_product, 2 as max_products, 'active' as subscription_status,
               NULL as current_period_start, NULL as current_period_end, FALSE as cancel_at_period_end,
               NULL as stripe_customer_id, NULL as stripe_subscription_id, 0 as current_products_count,
               FALSE as has_ai_enhancement, NULL as subscription_created_at, NULL as subscription_updated_at,
               p_user_id as queried_user_id;
    END;

    -- Validate input
    IF p_user_id IS NULL OR p_user_id <= 0 THEN
        SELECT 'error' as status, 'Valid user ID is required' as message,
               NULL as subscription_id, 'Free Plan' as plan_name, 'free' as plan_type, 0.00 as price_per_month,
               NULL as price_per_product, 2 as max_products, 'active' as subscription_status,
               NULL as current_period_start, NULL as current_period_end, FALSE as cancel_at_period_end,
               NULL as stripe_customer_id, NULL as stripe_subscription_id, 0 as current_products_count,
               FALSE as has_ai_enhancement, NULL as subscription_created_at, NULL as subscription_updated_at,
               p_user_id as queried_user_id;
    ELSE
        -- Check if user exists
        SELECT COUNT(*) INTO user_exists 
        FROM users 
        WHERE id = p_user_id AND is_active = TRUE;

        IF user_exists = 0 THEN
            SELECT 'error' as status, 'User not found or inactive' as message,
                   NULL as subscription_id, 'Free Plan' as plan_name, 'free' as plan_type, 0.00 as price_per_month,
                   NULL as price_per_product, 2 as max_products, 'active' as subscription_status,
                   NULL as current_period_start, NULL as current_period_end, FALSE as cancel_at_period_end,
                   NULL as stripe_customer_id, NULL as stripe_subscription_id, 0 as current_products_count,
                   FALSE as has_ai_enhancement, NULL as subscription_created_at, NULL as subscription_updated_at,
                   p_user_id as queried_user_id;
        ELSE
            -- Get current product count
            SELECT COUNT(*) INTO product_count 
            FROM user_products 
            WHERE user_id = p_user_id AND is_active = TRUE;
            
            -- Check if user has an active subscription
            SELECT COUNT(*) INTO has_subscription
            FROM user_subscriptions 
            WHERE user_id = p_user_id AND status = 'active';

            IF has_subscription > 0 THEN
                -- Return subscription details - FINALIZED column order
                SELECT 
                    'success' as status,                                        -- 0
                    'Subscription info retrieved successfully' as message,      -- 1
                    us.id as subscription_id,                                  -- 2
                    sp.plan_name,                                              -- 3
                    sp.plan_type,                                              -- 4
                    sp.price_per_month,                                        -- 5
                    sp.price_per_product,                                      -- 6
                    COALESCE(us.custom_product_limit, sp.max_products) as max_products, -- 7
                    us.status as subscription_status,                          -- 8
                    us.current_period_start,                                   -- 9
                    us.current_period_end,                                     -- 10
                    us.cancel_at_period_end,                                   -- 11
                    us.stripe_customer_id,                                     -- 12
                    us.stripe_subscription_id,                                 -- 13
                    product_count as current_products_count,                   -- 14
                    (SELECT COUNT(*) > 0 FROM user_subscription_addons usa 
                     JOIN subscription_addons sa ON usa.addon_id = sa.id 
                     WHERE usa.subscription_id = us.id AND usa.status = 'active' 
                     AND sa.addon_name = 'AI Enhancement') as has_ai_enhancement, -- 15
                    us.created_at as subscription_created_at,                  -- 16
                    us.updated_at as subscription_updated_at,                  -- 17
                    p_user_id as queried_user_id                               -- 18
                FROM user_subscriptions us
                JOIN subscription_plans sp ON us.plan_id = sp.id
                WHERE us.user_id = p_user_id AND us.status = 'active'
                LIMIT 1;
            ELSE
                -- No subscription found - return default free plan info
                SELECT 
                    'success' as status,                                -- 0
                    'Subscription info retrieved successfully' as message, -- 1
                    NULL as subscription_id,                            -- 2
                    'Free Plan' as plan_name,                           -- 3
                    'free' as plan_type,                                -- 4
                    0.00 as price_per_month,                            -- 5
                    NULL as price_per_product,                          -- 6
                    2 as max_products,                                  -- 7
                    'active' as subscription_status,                    -- 8
                    NULL as current_period_start,                       -- 9
                    NULL as current_period_end,                         -- 10
                    FALSE as cancel_at_period_end,                      -- 11
                    NULL as stripe_customer_id,                         -- 12
                    NULL as stripe_subscription_id,                     -- 13
                    product_count as current_products_count,            -- 14
                    FALSE as has_ai_enhancement,                        -- 15
                    NULL as subscription_created_at,                    -- 16
                    NULL as subscription_updated_at,                    -- 17
                    p_user_id as queried_user_id;                       -- 18
            END IF;
        END IF;
    END IF;
END//

-- ============================================================================
-- Procedure: check_product_limit
-- Description: Check if user can add more products based on their subscription
-- Used by: premium route - check limit
-- ============================================================================
DROP PROCEDURE IF EXISTS check_product_limit//

CREATE PROCEDURE check_product_limit(
    IN p_user_id INT
)
BEGIN
    DECLARE user_exists INT DEFAULT 0;
    DECLARE current_count INT DEFAULT 0;
    DECLARE max_allowed INT DEFAULT 2;
    DECLARE can_add BOOLEAN DEFAULT FALSE;
    DECLARE plan_type VARCHAR(50) DEFAULT 'free';
    DECLARE has_subscription INT DEFAULT 0;
    
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SELECT 'error' as status, 'Database error occurred while checking product limit' as message,
               FALSE as can_add_product, 0 as current_count, 0 as max_allowed;
    END;

    -- Validate input
    IF p_user_id IS NULL OR p_user_id <= 0 THEN
        SELECT 'error' as status, 'Valid user ID is required' as message,
               FALSE as can_add_product, 0 as current_count, 0 as max_allowed;
    ELSE
        -- Check if user exists
        SELECT COUNT(*) INTO user_exists 
        FROM users 
        WHERE id = p_user_id AND is_active = TRUE;

        IF user_exists = 0 THEN
            SELECT 'error' as status, 'User not found or inactive' as message,
                   FALSE as can_add_product, 0 as current_count, 0 as max_allowed;
        ELSE
            -- Get current product count
            SELECT COUNT(*) INTO current_count
            FROM user_products 
            WHERE user_id = p_user_id AND is_active = TRUE;

            -- Check if user has a subscription
            SELECT COUNT(*) INTO has_subscription
            FROM user_subscriptions 
            WHERE user_id = p_user_id AND status = 'active';

            IF has_subscription > 0 THEN
                -- Get user's subscription limits
                SELECT 
                    sp.plan_type,
                    COALESCE(us.custom_product_limit, sp.max_products) as max_products
                INTO plan_type, max_allowed
                FROM user_subscriptions us
                JOIN subscription_plans sp ON us.plan_id = sp.id
                WHERE us.user_id = p_user_id AND us.status = 'active'
                LIMIT 1;
            ELSE
                -- No subscription found, use default free limits
                SET max_allowed = 2;
                SET plan_type = 'free';
            END IF;

            -- Check if user can add more products
            IF plan_type = 'unlimited' OR max_allowed IS NULL THEN
                SET can_add = TRUE;
                SET max_allowed = -1; -- Indicate unlimited
            ELSEIF current_count < max_allowed THEN
                SET can_add = TRUE;
            ELSE
                SET can_add = FALSE;
            END IF;

            SELECT 'success' as status, 'Product limit checked successfully' as message,
                   can_add as can_add_product, 
                   current_count, 
                   max_allowed,
                   plan_type,
                   p_user_id as checked_user_id;
        END IF;
    END IF;
END//

-- ============================================================================
-- Procedure: get_all_subscription_plans
-- Description: Get all available subscription plans and addons
-- Used by: premium route - get plans
-- ============================================================================
DROP PROCEDURE IF EXISTS get_all_subscription_plans//

CREATE PROCEDURE get_all_subscription_plans()
BEGIN
    DECLARE plan_count INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SELECT 'error' as status, 'Database error occurred while retrieving plans' as message;
    END;

    -- Check if any plans exist
    SELECT COUNT(*) INTO plan_count FROM subscription_plans WHERE is_active = TRUE;

    SELECT 'success' as status, 'Plans retrieved successfully' as message;

    IF plan_count > 0 THEN
        -- Return subscription plans from database
        SELECT 
            id,
            plan_name,
            plan_type,
            price_per_month,
            price_per_product,
            max_products,
            stripe_price_id,
            is_active,
            'plan' as record_type
        FROM subscription_plans
        WHERE is_active = TRUE
        ORDER BY 
            CASE plan_type 
                WHEN 'free' THEN 1
                WHEN 'pay_as_you_go' THEN 2
                WHEN 'unlimited' THEN 3
                ELSE 4
            END;
    ELSE
        -- Return default plans if none exist
        SELECT 
            0 as id,
            'Free Plan' as plan_name,
            'free' as plan_type,
            0.00 as price_per_month,
            NULL as price_per_product,
            2 as max_products,
            NULL as stripe_price_id,
            TRUE as is_active,
            'plan' as record_type
        UNION ALL
        SELECT 
            0 as id,
            'Pay-as-you-go' as plan_name,
            'pay_as_you_go' as plan_type,
            0.00 as price_per_month,
            5.00 as price_per_product,
            NULL as max_products,
            NULL as stripe_price_id,
            TRUE as is_active,
            'plan' as record_type
        UNION ALL
        SELECT 
            0 as id,
            'Unlimited Access' as plan_name,
            'unlimited' as plan_type,
            145.00 as price_per_month,
            NULL as price_per_product,
            NULL as max_products,
            NULL as stripe_price_id,
            TRUE as is_active,
            'plan' as record_type;
    END IF;

    -- Return available addons
    SELECT 
        id,
        addon_name,
        addon_description,
        price_per_month,
        stripe_price_id,
        is_active,
        'addon' as record_type
    FROM subscription_addons
    WHERE is_active = TRUE
    ORDER BY addon_name;
END//

-- ============================================================================
-- Procedure: create_user_subscription
-- Description: Create or update user subscription
-- Used by: premium route - process checkout success
-- ============================================================================
DROP PROCEDURE IF EXISTS create_user_subscription//

CREATE PROCEDURE create_user_subscription(
    IN p_user_id INT,
    IN p_plan_type VARCHAR(50),
    IN p_custom_product_limit INT,
    IN p_stripe_customer_id VARCHAR(255),
    IN p_stripe_subscription_id VARCHAR(255),
    IN p_stripe_session_id VARCHAR(255),
    IN p_period_start TIMESTAMP,
    IN p_period_end TIMESTAMP
)
BEGIN
    DECLARE user_exists INT DEFAULT 0;
    DECLARE plan_id INT DEFAULT 0;
    DECLARE existing_subscription_id INT DEFAULT 0;
    DECLARE new_subscription_id INT DEFAULT 0;
    
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT 'error' as status, 'Database error occurred while creating subscription' as message, 0 as subscription_id;
    END;

    START TRANSACTION;

    -- Validate input
    IF p_user_id IS NULL OR p_user_id <= 0 THEN
        SELECT 'error' as status, 'Valid user ID is required' as message, 0 as subscription_id;
        ROLLBACK;
    ELSEIF p_plan_type IS NULL OR p_plan_type = '' THEN
        SELECT 'error' as status, 'Plan type is required' as message, 0 as subscription_id;
        ROLLBACK;
    ELSE
        -- Check if user exists
        SELECT COUNT(*) INTO user_exists 
        FROM users 
        WHERE id = p_user_id AND is_active = TRUE;

        IF user_exists = 0 THEN
            SELECT 'error' as status, 'User not found or inactive' as message, 0 as subscription_id;
            ROLLBACK;
        ELSE
            -- Get plan ID
            SELECT id INTO plan_id
            FROM subscription_plans
            WHERE plan_type = p_plan_type AND is_active = TRUE
            LIMIT 1;

            IF plan_id IS NULL OR plan_id = 0 THEN
                -- Plan doesn't exist, try to create it
                IF p_plan_type = 'free' THEN
                    INSERT INTO subscription_plans (plan_name, plan_type, price_per_month, max_products)
                    VALUES ('Free Plan', 'free', 0.00, 2);
                ELSEIF p_plan_type = 'pay_as_you_go' THEN
                    INSERT INTO subscription_plans (plan_name, plan_type, price_per_month, price_per_product)
                    VALUES ('Pay-as-you-go', 'pay_as_you_go', 0.00, 5.00);
                ELSEIF p_plan_type = 'unlimited' THEN
                    INSERT INTO subscription_plans (plan_name, plan_type, price_per_month)
                    VALUES ('Unlimited Access', 'unlimited', 145.00);
                END IF;
                
                SET plan_id = LAST_INSERT_ID();
            END IF;

            IF plan_id = 0 THEN
                SELECT 'error' as status, 'Invalid plan type' as message, 0 as subscription_id;
                ROLLBACK;
            ELSE
                -- Cancel existing active subscription
                UPDATE user_subscriptions 
                SET status = 'cancelled', updated_at = NOW()
                WHERE user_id = p_user_id AND status = 'active';

                -- Create new subscription
                INSERT INTO user_subscriptions (
                    user_id,
                    plan_id,
                    custom_product_limit,
                    stripe_customer_id,
                    stripe_subscription_id,
                    stripe_session_id,
                    status,
                    current_period_start,
                    current_period_end,
                    created_at,
                    updated_at
                ) VALUES (
                    p_user_id,
                    plan_id,
                    p_custom_product_limit,
                    p_stripe_customer_id,
                    p_stripe_subscription_id,
                    p_stripe_session_id,
                    'active',
                    p_period_start,
                    p_period_end,
                    NOW(),
                    NOW()
                );

                SET new_subscription_id = LAST_INSERT_ID();

                SELECT 'success' as status, 'Subscription created successfully' as message, 
                       new_subscription_id as subscription_id, p_plan_type as created_plan_type,
                       p_user_id as subscribed_user_id, plan_id as assigned_plan_id;
                COMMIT;
            END IF;
        END IF;
    END IF;
END//

-- ============================================================================
-- Procedure: add_subscription_addon
-- Description: Add an addon to user's subscription
-- Used by: premium route - process checkout success
-- ============================================================================
DROP PROCEDURE IF EXISTS add_subscription_addon//

CREATE PROCEDURE add_subscription_addon(
    IN p_subscription_id INT,
    IN p_addon_name VARCHAR(100),
    IN p_stripe_subscription_item_id VARCHAR(255)
)
BEGIN
    DECLARE addon_id INT DEFAULT 0;
    DECLARE subscription_exists INT DEFAULT 0;
    DECLARE addon_exists INT DEFAULT 0;
    
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT 'error' as status, 'Database error occurred while adding addon' as message;
    END;

    START TRANSACTION;

    -- Validate input
    IF p_subscription_id IS NULL OR p_subscription_id <= 0 THEN
        SELECT 'error' as status, 'Valid subscription ID is required' as message;
        ROLLBACK;
    ELSEIF p_addon_name IS NULL OR p_addon_name = '' THEN
        SELECT 'error' as status, 'Addon name is required' as message;
        ROLLBACK;
    ELSE
        -- Check if subscription exists
        SELECT COUNT(*) INTO subscription_exists
        FROM user_subscriptions
        WHERE id = p_subscription_id AND status = 'active';

        IF subscription_exists = 0 THEN
            SELECT 'error' as status, 'Subscription not found or inactive' as message;
            ROLLBACK;
        ELSE
            -- Get addon ID
            SELECT id INTO addon_id
            FROM subscription_addons
            WHERE addon_name = p_addon_name AND is_active = TRUE
            LIMIT 1;

            IF addon_id IS NULL OR addon_id = 0 THEN
                -- Create AI Enhancement addon if it doesn't exist
                IF p_addon_name = 'AI Enhancement' THEN
                    INSERT INTO subscription_addons (addon_name, addon_description, price_per_month)
                    VALUES ('AI Enhancement', 'Advanced AI failsafe tracking using ChatGPT, Claude AI & other models for 99% accuracy guarantee', 50.00);
                    SET addon_id = LAST_INSERT_ID();
                END IF;
            END IF;

            IF addon_id = 0 THEN
                SELECT 'error' as status, 'Addon not found' as message;
                ROLLBACK;
            ELSE
                -- Check if addon already exists for this subscription
                SELECT COUNT(*) INTO addon_exists
                FROM user_subscription_addons
                WHERE subscription_id = p_subscription_id AND addon_id = addon_id AND status = 'active';

                IF addon_exists > 0 THEN
                    SELECT 'error' as status, 'Addon already exists for this subscription' as message;
                    ROLLBACK;
                ELSE
                    -- Add the addon
                    INSERT INTO user_subscription_addons (
                        subscription_id,
                        addon_id,
                        stripe_subscription_item_id,
                        status,
                        created_at,
                        updated_at
                    ) VALUES (
                        p_subscription_id,
                        addon_id,
                        p_stripe_subscription_item_id,
                        'active',
                        NOW(),
                        NOW()
                    );

                    SELECT 'success' as status, 'Addon added successfully' as message,
                           p_addon_name as added_addon_name, p_subscription_id as addon_subscription_id,
                           addon_id as assigned_addon_id;
                    COMMIT;
                END IF;
            END IF;
        END IF;
    END IF;
END//

-- ============================================================================
-- Procedure: cancel_user_subscription
-- Description: Cancel user's subscription
-- Used by: premium route - cancel subscription
-- ============================================================================
DROP PROCEDURE IF EXISTS cancel_user_subscription//

CREATE PROCEDURE cancel_user_subscription(
    IN p_user_id INT,
    IN p_cancel_immediately BOOLEAN
)
BEGIN
    DECLARE user_exists INT DEFAULT 0;
    DECLARE subscription_exists INT DEFAULT 0;
    
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT 'error' as status, 'Database error occurred while cancelling subscription' as message;
    END;

    START TRANSACTION;

    -- Validate input
    IF p_user_id IS NULL OR p_user_id <= 0 THEN
        SELECT 'error' as status, 'Valid user ID is required' as message;
        ROLLBACK;
    ELSE
        -- Check if user exists
        SELECT COUNT(*) INTO user_exists 
        FROM users 
        WHERE id = p_user_id AND is_active = TRUE;

        IF user_exists = 0 THEN
            SELECT 'error' as status, 'User not found or inactive' as message;
            ROLLBACK;
        ELSE
            -- Check if active subscription exists
            SELECT COUNT(*) INTO subscription_exists
            FROM user_subscriptions
            WHERE user_id = p_user_id AND status = 'active';

            IF subscription_exists = 0 THEN
                SELECT 'error' as status, 'No active subscription found' as message;
                ROLLBACK;
            ELSE
                IF p_cancel_immediately = TRUE THEN
                    -- Cancel immediately
                    UPDATE user_subscriptions 
                    SET status = 'cancelled', updated_at = NOW()
                    WHERE user_id = p_user_id AND status = 'active';

                    -- Try to create free subscription if a free plan exists
                    SELECT id INTO subscription_exists  -- Reusing variable
                    FROM subscription_plans
                    WHERE plan_type = 'free' AND is_active = TRUE
                    LIMIT 1;

                    IF subscription_exists IS NOT NULL THEN
                        INSERT INTO user_subscriptions (user_id, plan_id, status, created_at, updated_at)
                        VALUES (p_user_id, subscription_exists, 'active', NOW(), NOW());
                    END IF;
                    -- If no free plan exists, user will have no active subscription

                    -- Cancel all addons
                    UPDATE user_subscription_addons usa
                    JOIN user_subscriptions us ON usa.subscription_id = us.id
                    SET usa.status = 'cancelled', usa.updated_at = NOW()
                    WHERE us.user_id = p_user_id;

                    SELECT 'success' as status, 'Subscription cancelled immediately' as message,
                           p_user_id as cancelled_user_id, 'immediate' as cancellation_type;
                ELSE
                    -- Mark for cancellation at period end
                    UPDATE user_subscriptions 
                    SET cancel_at_period_end = TRUE, updated_at = NOW()
                    WHERE user_id = p_user_id AND status = 'active';

                    SELECT 'success' as status, 'Subscription will be cancelled at the end of current period' as message,
                           p_user_id as cancelled_user_id, 'end_of_period' as cancellation_type;
                END IF;

                COMMIT;
            END IF;
        END IF;
    END IF;
END//

-- ============================================================================
-- PRODUCT MANAGEMENT PROCEDURES - BACKWARD COMPATIBLE
-- ============================================================================

-- ============================================================================
-- Procedure: get_user_products
-- Description: Get all products tracked by a user (basic version)
-- Backward compatibility wrapper for get_user_products_with_data
-- ============================================================================
DROP PROCEDURE IF EXISTS get_user_products//

CREATE PROCEDURE get_user_products(
    IN p_user_id INT
)
BEGIN
    -- Call the enhanced version but return compatible format
    CALL get_user_products_with_data(p_user_id);
END//

-- ============================================================================
-- Procedure: get_user_products_with_data
-- Description: Get all products tracked by a user (enhanced version with webhooks and SMS)
-- Used by: dashboard route - get products
-- FINALIZED: Column order matches Python parsing expectations
-- ============================================================================
DROP PROCEDURE IF EXISTS get_user_products_with_data//

CREATE PROCEDURE get_user_products_with_data(
    IN p_user_id INT
)
BEGIN
    DECLARE user_exists INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SELECT 'error' as status, 'Database error occurred while retrieving products' as message,
               NULL as id, NULL as product_url, NULL as product_title, NULL as store_name,
               NULL as current_price, NULL as min_price_alert, NULL as max_price_alert,
               NULL as discord_webhook_url, NULL as alerts_sent, NULL as product_status, 
               NULL as last_checked_at, NULL as last_price_change, NULL as sms_notifications_enabled,
               NULL as created_at, NULL as updated_at, NULL as price_history_count, NULL as queried_user_id;
    END;

    -- Validate input
    IF p_user_id IS NULL OR p_user_id <= 0 THEN
        SELECT 'error' as status, 'Valid user ID is required' as message,
               NULL as id, NULL as product_url, NULL as product_title, NULL as store_name,
               NULL as current_price, NULL as min_price_alert, NULL as max_price_alert,
               NULL as discord_webhook_url, NULL as alerts_sent, NULL as product_status,
               NULL as last_checked_at, NULL as last_price_change, NULL as sms_notifications_enabled,
               NULL as created_at, NULL as updated_at, NULL as price_history_count, NULL as queried_user_id;
    ELSE
        -- Check if user exists
        SELECT COUNT(*) INTO user_exists 
        FROM users 
        WHERE id = p_user_id AND is_active = TRUE;

        IF user_exists = 0 THEN
            SELECT 'error' as status, 'User not found or inactive' as message,
                   NULL as id, NULL as product_url, NULL as product_title, NULL as store_name,
                   NULL as current_price, NULL as min_price_alert, NULL as max_price_alert,
                   NULL as discord_webhook_url, NULL as alerts_sent, NULL as product_status,
                   NULL as last_checked_at, NULL as last_price_change, NULL as sms_notifications_enabled,
                   NULL as created_at, NULL as updated_at, NULL as price_history_count, NULL as queried_user_id;
        ELSE
            -- Return user's products - FINALIZED column order to match Python expectations
            SELECT 
                'success' as status,                                                    -- 0
                'Products retrieved successfully' as message,                           -- 1
                up.id,                                                                 -- 2
                up.product_url,                                                        -- 3
                up.product_title,                                                      -- 4
                up.store_name,                                                         -- 5
                up.current_price,                                                      -- 6
                up.min_price_alert,                                                    -- 7
                up.max_price_alert,                                                    -- 8
                up.discord_webhook_url,                                                -- 9
                up.alerts_sent,                                                        -- 10
                up.status as product_status,                                           -- 11
                up.last_checked_at,                                                    -- 12
                up.last_price_change,                                                  -- 13
                up.sms_notifications_enabled,                                          -- 14
                up.created_at,                                                         -- 15
                up.updated_at,                                                         -- 16
                (SELECT COUNT(*) FROM product_price_history WHERE product_id = up.id) as price_history_count, -- 17
                p_user_id as queried_user_id                                           -- 18
            FROM user_products up
            WHERE up.user_id = p_user_id AND up.is_active = TRUE
            ORDER BY up.created_at DESC;
        END IF;
    END IF;
END//

-- ============================================================================
-- Procedure: add_user_product
-- Description: Add a new product for tracking (basic version)
-- Backward compatibility wrapper
-- ============================================================================
DROP PROCEDURE IF EXISTS add_user_product//

CREATE PROCEDURE add_user_product(
    IN p_user_id INT,
    IN p_product_url VARCHAR(1000),
    IN p_product_title VARCHAR(500)
)
BEGIN
    -- Call the enhanced version with NULL values for new parameters
    CALL add_user_product_with_webhook(p_user_id, p_product_url, p_product_title, NULL, FALSE);
END//

-- ============================================================================
-- Procedure: add_user_product_with_webhook
-- Description: Add a new product for tracking WITH PREMIUM LIMIT CHECKING and SMS
-- Used by: dashboard route - add product
-- ============================================================================
DROP PROCEDURE IF EXISTS add_user_product_with_webhook//

CREATE PROCEDURE add_user_product_with_webhook(
    IN p_user_id INT,
    IN p_product_url VARCHAR(1000),
    IN p_product_title VARCHAR(500),
    IN p_discord_webhook_url VARCHAR(500),
    IN p_sms_notifications_enabled BOOLEAN
)
BEGIN
    DECLARE user_exists INT DEFAULT 0;
    DECLARE product_exists INT DEFAULT 0;
    DECLARE new_product_id INT DEFAULT 0;
    DECLARE current_count INT DEFAULT 0;
    DECLARE max_allowed INT DEFAULT 2;
    DECLARE can_add BOOLEAN DEFAULT FALSE;
    DECLARE plan_type VARCHAR(50) DEFAULT 'free';
    DECLARE store_name VARCHAR(100) DEFAULT '';
    
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT 'error' as status, 'Database error occurred while adding product' as message, 0 as product_id;
    END;

    START TRANSACTION;

    -- Validate input parameters
    IF p_user_id IS NULL OR p_user_id <= 0 THEN
        SELECT 'error' as status, 'Valid user ID is required' as message, 0 as product_id;
        ROLLBACK;
    ELSEIF p_product_url IS NULL OR TRIM(p_product_url) = '' THEN
        SELECT 'error' as status, 'Product URL is required' as message, 0 as product_id;
        ROLLBACK;
    ELSE
        -- Check if user exists
        SELECT COUNT(*) INTO user_exists 
        FROM users 
        WHERE id = p_user_id AND is_active = TRUE;

        IF user_exists = 0 THEN
            SELECT 'error' as status, 'User not found or inactive' as message, 0 as product_id;
            ROLLBACK;
        ELSE
            -- Check product limits first
            SELECT COUNT(*) INTO current_count
            FROM user_products 
            WHERE user_id = p_user_id AND is_active = TRUE;

            -- Check if user has a subscription
            SELECT COUNT(*) INTO product_exists  -- Reusing variable temporarily
            FROM user_subscriptions 
            WHERE user_id = p_user_id AND status = 'active';

            IF product_exists > 0 THEN
                -- Get user's subscription limits
                SELECT 
                    sp.plan_type,
                    COALESCE(us.custom_product_limit, sp.max_products) as max_products
                INTO plan_type, max_allowed
                FROM user_subscriptions us
                JOIN subscription_plans sp ON us.plan_id = sp.id
                WHERE us.user_id = p_user_id AND us.status = 'active'
                LIMIT 1;
            ELSE
                -- No subscription found, use default free limits
                SET max_allowed = 2;
                SET plan_type = 'free';
            END IF;

            -- Check if user can add more products
            IF plan_type = 'unlimited' OR max_allowed IS NULL THEN
                SET can_add = TRUE;
            ELSEIF current_count < max_allowed THEN
                SET can_add = TRUE;
            ELSE
                SET can_add = FALSE;
            END IF;

            IF can_add = FALSE THEN
                SELECT 'error' as status, 'Product limit reached. Please upgrade your subscription to add more products.' as message, 
                       0 as product_id, current_count as user_current_count, max_allowed as user_max_allowed, plan_type as user_plan_type;
                ROLLBACK;
            ELSE
                -- Check if product URL already exists for this user
                SELECT COUNT(*) INTO product_exists 
                FROM user_products 
                WHERE user_id = p_user_id AND product_url = p_product_url AND is_active = TRUE;

                IF product_exists > 0 THEN
                    SELECT 'error' as status, 'This product is already being tracked' as message, 0 as product_id;
                    ROLLBACK;
                ELSE
                    -- Extract store name from URL
                    SET store_name = CASE
                        WHEN p_product_url LIKE '%amazon.%' THEN 'Amazon'
                        WHEN p_product_url LIKE '%ebay.%' THEN 'eBay'
                        WHEN p_product_url LIKE '%bestbuy.%' THEN 'Best Buy'
                        WHEN p_product_url LIKE '%target.%' THEN 'Target'
                        WHEN p_product_url LIKE '%walmart.%' THEN 'Walmart'
                        ELSE 'Other'
                    END;

                    -- Insert new product
                    INSERT INTO user_products (
                        user_id, 
                        product_url, 
                        product_title, 
                        store_name,
                        discord_webhook_url,
                        sms_notifications_enabled,
                        status,
                        created_at,
                        updated_at
                    ) VALUES (
                        p_user_id,
                        TRIM(p_product_url),
                        COALESCE(NULLIF(TRIM(p_product_title), ''), CONCAT(store_name, ' Product')),
                        store_name,
                        NULLIF(TRIM(p_discord_webhook_url), ''),
                        COALESCE(p_sms_notifications_enabled, FALSE),
                        'checking',
                        NOW(),
                        NOW()
                    );

                    SET new_product_id = LAST_INSERT_ID();

                    -- Log the activity
                    INSERT INTO user_activity_log (user_id, activity_type, success, created_at)
                    VALUES (p_user_id, 'product_added', TRUE, NOW());

                    SELECT 'success' as status, 'Product added successfully' as message, 
                           new_product_id as product_id, store_name as detected_store,
                           current_count + 1 as new_product_count, max_allowed as remaining_limit,
                           plan_type as user_plan_type;
                    COMMIT;
                END IF;
            END IF;
        END IF;
    END IF;
END//

-- ============================================================================
-- Procedure: update_user_product
-- Description: Update product settings (basic version)
-- Backward compatibility wrapper
-- ============================================================================
DROP PROCEDURE IF EXISTS update_user_product//

CREATE PROCEDURE update_user_product(
    IN p_user_id INT,
    IN p_product_id INT,
    IN p_min_price_alert DECIMAL(10,2),
    IN p_max_price_alert DECIMAL(10,2)
)
BEGIN
    -- Call the enhanced version with NULL values for new parameters
    CALL update_user_product_with_webhook(p_user_id, p_product_id, p_min_price_alert, p_max_price_alert, NULL, NULL);
END//

-- ============================================================================
-- Procedure: update_user_product_with_webhook
-- Description: Update product settings with webhook and SMS support
-- Used by: dashboard route - update product
-- ============================================================================
DROP PROCEDURE IF EXISTS update_user_product_with_webhook//

CREATE PROCEDURE update_user_product_with_webhook(
    IN p_user_id INT,
    IN p_product_id INT,
    IN p_min_price_alert DECIMAL(10,2),
    IN p_max_price_alert DECIMAL(10,2),
    IN p_discord_webhook_url VARCHAR(500),
    IN p_sms_notifications_enabled BOOLEAN
)
BEGIN
    DECLARE product_exists INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT 'error' as status, 'Database error occurred while updating product' as message;
    END;

    START TRANSACTION;

    -- Validate input parameters
    IF p_user_id IS NULL OR p_user_id <= 0 THEN
        SELECT 'error' as status, 'Valid user ID is required' as message;
        ROLLBACK;
    ELSEIF p_product_id IS NULL OR p_product_id <= 0 THEN
        SELECT 'error' as status, 'Valid product ID is required' as message;
        ROLLBACK;
    ELSE
        -- Check if product exists and belongs to user
        SELECT COUNT(*) INTO product_exists 
        FROM user_products 
        WHERE id = p_product_id AND user_id = p_user_id AND is_active = TRUE;

        IF product_exists = 0 THEN
            SELECT 'error' as status, 'Product not found or access denied' as message;
            ROLLBACK;
        ELSE
            -- Validate price alerts
            IF p_min_price_alert IS NOT NULL AND p_max_price_alert IS NOT NULL AND p_min_price_alert >= p_max_price_alert THEN
                SELECT 'error' as status, 'Minimum price alert must be less than maximum price alert' as message;
                ROLLBACK;
            ELSE
                -- Update product settings
                UPDATE user_products 
                SET min_price_alert = p_min_price_alert,
                    max_price_alert = p_max_price_alert,
                    discord_webhook_url = NULLIF(TRIM(p_discord_webhook_url), ''),
                    sms_notifications_enabled = COALESCE(p_sms_notifications_enabled, sms_notifications_enabled),
                    updated_at = NOW()
                WHERE id = p_product_id AND user_id = p_user_id;

                SELECT 'success' as status, 'Product settings updated successfully' as message,
                       p_product_id as updated_product_id, p_user_id as owner_user_id,
                       p_min_price_alert as set_min_price, p_max_price_alert as set_max_price,
                       NULLIF(TRIM(p_discord_webhook_url), '') as set_webhook_url,
                       p_sms_notifications_enabled as set_sms_enabled;
                COMMIT;
            END IF;
        END IF;
    END IF;
END//

-- ============================================================================
-- Procedure: delete_user_product
-- Description: Delete/deactivate a user's product
-- Used by: dashboard route - delete product
-- ============================================================================
DROP PROCEDURE IF EXISTS delete_user_product//

CREATE PROCEDURE delete_user_product(
    IN p_user_id INT,
    IN p_product_id INT
)
BEGIN
    DECLARE product_exists INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT 'error' as status, 'Database error occurred while deleting product' as message;
    END;

    START TRANSACTION;

    -- Validate input parameters
    IF p_user_id IS NULL OR p_user_id <= 0 THEN
        SELECT 'error' as status, 'Valid user ID is required' as message;
        ROLLBACK;
    ELSEIF p_product_id IS NULL OR p_product_id <= 0 THEN
        SELECT 'error' as status, 'Valid product ID is required' as message;
        ROLLBACK;
    ELSE
        -- Check if product exists and belongs to user
        SELECT COUNT(*) INTO product_exists 
        FROM user_products 
        WHERE id = p_product_id AND user_id = p_user_id AND is_active = TRUE;

        IF product_exists = 0 THEN
            SELECT 'error' as status, 'Product not found or access denied' as message;
            ROLLBACK;
        ELSE
            -- Soft delete (deactivate) the product
            UPDATE user_products 
            SET is_active = FALSE,
                updated_at = NOW()
            WHERE id = p_product_id AND user_id = p_user_id;

            -- Log the activity
            INSERT INTO user_activity_log (user_id, activity_type, success, created_at)
            VALUES (p_user_id, 'product_deleted', TRUE, NOW());

            SELECT 'success' as status, 'Product removed successfully' as message,
                   p_product_id as deleted_product_id, p_user_id as owner_user_id;
            COMMIT;
        END IF;
    END IF;
END//

-- ============================================================================
-- SETTINGS PROCEDURES
-- ============================================================================

-- ============================================================================
-- Procedure: get_user_settings
-- Description: Get user's settings including phone number
-- Used by: dashboard route - get settings
-- ============================================================================
DROP PROCEDURE IF EXISTS get_user_settings//

CREATE PROCEDURE get_user_settings(
    IN p_user_id INT
)
BEGIN
    DECLARE user_exists INT DEFAULT 0;
    DECLARE settings_exists INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SELECT 'error' as status, 'Database error occurred while retrieving settings' as message;
    END;

    -- Validate input
    IF p_user_id IS NULL OR p_user_id <= 0 THEN
        SELECT 'error' as status, 'Valid user ID is required' as message;
    ELSE
        -- Check if user exists
        SELECT COUNT(*) INTO user_exists 
        FROM users 
        WHERE id = p_user_id AND is_active = TRUE;

        IF user_exists = 0 THEN
            SELECT 'error' as status, 'User not found or inactive' as message;
        ELSE
            -- Check if settings exist
            SELECT COUNT(*) INTO settings_exists 
            FROM user_settings 
            WHERE user_id = p_user_id;

            IF settings_exists = 0 THEN
                -- Create default settings
                INSERT INTO user_settings (user_id) VALUES (p_user_id);
            END IF;

            -- Return user's settings
            SELECT 'success' as status, 'Settings retrieved successfully' as message;
            
            SELECT 
                email_notifications,
                discord_webhook_url,
                phone_number,
                sms_notifications,
                notification_frequency,
                price_drop_alerts,
                restock_alerts,
                price_increase_alerts,
                dashboard_theme,
                items_per_page,
                default_currency,
                share_data,
                public_profile,
                created_at,
                updated_at,
                p_user_id as settings_user_id
            FROM user_settings
            WHERE user_id = p_user_id;
        END IF;
    END IF;
END//

-- ============================================================================
-- Procedure: update_user_settings
-- Description: Update user's settings including phone number
-- Used by: dashboard route - update settings
-- FINALIZED: Accept all 14 parameters with defaults for backward compatibility
-- ============================================================================
DROP PROCEDURE IF EXISTS update_user_settings//

CREATE PROCEDURE update_user_settings(
    IN p_user_id INT,
    IN p_email_notifications BOOLEAN,
    IN p_discord_webhook_url VARCHAR(500),
    IN p_notification_frequency ENUM('instant', 'hourly', 'daily'),
    IN p_price_drop_alerts BOOLEAN,
    IN p_restock_alerts BOOLEAN,
    IN p_price_increase_alerts BOOLEAN,
    IN p_dashboard_theme ENUM('light', 'dark', 'auto'),
    IN p_items_per_page INT,
    IN p_default_currency VARCHAR(3),
    IN p_share_data BOOLEAN,
    IN p_public_profile BOOLEAN,
    IN p_phone_number VARCHAR(20),           -- Position 13
    IN p_sms_notifications BOOLEAN           -- Position 14
)
BEGIN
    DECLARE user_exists INT DEFAULT 0;
    DECLARE settings_exists INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT 'error' as status, 'Database error occurred while updating settings' as message;
    END;

    START TRANSACTION;

    -- Validate input
    IF p_user_id IS NULL OR p_user_id <= 0 THEN
        SELECT 'error' as status, 'Valid user ID is required' as message;
        ROLLBACK;
    ELSE
        -- Check if user exists
        SELECT COUNT(*) INTO user_exists 
        FROM users 
        WHERE id = p_user_id AND is_active = TRUE;

        IF user_exists = 0 THEN
            SELECT 'error' as status, 'User not found or inactive' as message;
            ROLLBACK;
        ELSE
            -- Check if settings exist
            SELECT COUNT(*) INTO settings_exists 
            FROM user_settings 
            WHERE user_id = p_user_id;

            IF settings_exists = 0 THEN
                -- Create settings record
                INSERT INTO user_settings (user_id) VALUES (p_user_id);
            END IF;

            -- Validate Discord webhook URL if provided
            IF p_discord_webhook_url IS NOT NULL AND TRIM(p_discord_webhook_url) != '' THEN
                IF p_discord_webhook_url NOT LIKE 'https://discord.com/api/webhooks/%' AND 
                   p_discord_webhook_url NOT LIKE 'https://discordapp.com/api/webhooks/%' THEN
                    SELECT 'error' as status, 'Invalid Discord webhook URL format' as message;
                    ROLLBACK;
                END IF;
            END IF;

            -- Validate phone number if provided (basic validation)
            IF p_phone_number IS NOT NULL AND TRIM(p_phone_number) != '' THEN
                -- Remove non-numeric characters for validation
                IF LENGTH(REGEXP_REPLACE(p_phone_number, '[^0-9]', '')) < 10 THEN
                    SELECT 'error' as status, 'Invalid phone number format' as message;
                    ROLLBACK;
                END IF;
            END IF;

            -- Update settings - all columns for backward compatibility
            UPDATE user_settings 
            SET email_notifications = COALESCE(p_email_notifications, email_notifications),
                discord_webhook_url = CASE 
                    WHEN p_discord_webhook_url = '' THEN NULL 
                    ELSE COALESCE(p_discord_webhook_url, discord_webhook_url) 
                END,
                notification_frequency = COALESCE(p_notification_frequency, notification_frequency),
                price_drop_alerts = COALESCE(p_price_drop_alerts, price_drop_alerts),
                restock_alerts = COALESCE(p_restock_alerts, restock_alerts),
                price_increase_alerts = COALESCE(p_price_increase_alerts, price_increase_alerts),
                dashboard_theme = COALESCE(p_dashboard_theme, dashboard_theme),
                items_per_page = COALESCE(p_items_per_page, items_per_page),
                default_currency = COALESCE(p_default_currency, default_currency),
                share_data = COALESCE(p_share_data, share_data),
                public_profile = COALESCE(p_public_profile, public_profile),
                phone_number = CASE 
                    WHEN p_phone_number = '' THEN NULL 
                    ELSE COALESCE(p_phone_number, phone_number) 
                END,
                sms_notifications = COALESCE(p_sms_notifications, sms_notifications),
                updated_at = NOW()
            WHERE user_id = p_user_id;

            -- Log the activity
            INSERT INTO user_activity_log (user_id, activity_type, success, created_at)
            VALUES (p_user_id, 'settings_updated', TRUE, NOW());

            SELECT 'success' as status, 'Settings updated successfully' as message,
                   p_user_id as updated_settings_user_id, 
                   COALESCE(p_dashboard_theme, 'unchanged') as theme_setting,
                   COALESCE(p_notification_frequency, 'unchanged') as notification_setting;
            COMMIT;
        END IF;
    END IF;
END//

-- ============================================================================
-- OTHER PROCEDURES
-- ============================================================================

-- ============================================================================
-- Procedure: update_user_activity
-- Description: Log user activity
-- ============================================================================
DROP PROCEDURE IF EXISTS update_user_activity//

CREATE PROCEDURE update_user_activity(
    IN p_user_id INT,
    IN p_activity_type VARCHAR(50)
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SELECT 'error' as status, 'Database error occurred while logging activity' as message;
    END;

    -- Log the activity
    INSERT INTO user_activity_log (user_id, activity_type, success, created_at)
    VALUES (p_user_id, p_activity_type, TRUE, NOW());

    SELECT 'success' as status, 'Activity logged successfully' as message;
END//

-- ============================================================================
-- Procedure: get_user_by_email
-- Description: Get user information by email address
-- ============================================================================
DROP PROCEDURE IF EXISTS get_user_by_email//

CREATE PROCEDURE get_user_by_email(
    IN p_email VARCHAR(255)
)
BEGIN
    DECLARE user_count INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SELECT 'error' as status, 'Database error occurred while retrieving user' as message,
               0 as user_id, '' as full_name, FALSE as is_active;
    END;

    -- Validate input
    IF p_email IS NULL OR TRIM(p_email) = '' THEN
        SELECT 'error' as status, 'Email address is required' as message,
               0 as user_id, '' as full_name, FALSE as is_active;
    ELSE
        -- Check if user exists
        SELECT COUNT(*) INTO user_count 
        FROM users 
        WHERE email = LOWER(TRIM(p_email));

        IF user_count = 0 THEN
            SELECT 'error' as status, 'User not found' as message,
                   0 as user_id, '' as full_name, FALSE as is_active;
        ELSE
            -- Return user information
            SELECT 'success' as status,
                   'User found' as message,
                   id as user_id,
                   full_name,
                   is_active,
                   email as found_email
            FROM users 
            WHERE email = LOWER(TRIM(p_email))
            LIMIT 1;
        END IF;
    END IF;
END//

-- ============================================================================
-- Procedure: record_payment
-- Description: Record a payment transaction
-- ============================================================================
DROP PROCEDURE IF EXISTS record_payment//

CREATE PROCEDURE record_payment(
    IN p_user_id INT,
    IN p_subscription_id INT,
    IN p_stripe_payment_intent_id VARCHAR(255),
    IN p_amount DECIMAL(10,2),
    IN p_currency VARCHAR(3),
    IN p_payment_status VARCHAR(50),
    IN p_description TEXT
)
BEGIN
    DECLARE user_exists INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT 'error' as status, 'Database error occurred while recording payment' as message;
    END;

    START TRANSACTION;

    -- Validate input
    IF p_user_id IS NULL OR p_user_id <= 0 THEN
        SELECT 'error' as status, 'Valid user ID is required' as message;
        ROLLBACK;
    ELSEIF p_amount IS NULL OR p_amount <= 0 THEN
        SELECT 'error' as status, 'Valid amount is required' as message;
        ROLLBACK;
    ELSE
        -- Check if user exists
        SELECT COUNT(*) INTO user_exists 
        FROM users 
        WHERE id = p_user_id AND is_active = TRUE;

        IF user_exists = 0 THEN
            SELECT 'error' as status, 'User not found or inactive' as message;
            ROLLBACK;
        ELSE
            -- Insert payment record
            INSERT INTO payment_history (
                user_id,
                subscription_id,
                stripe_payment_intent_id,
                amount,
                currency,
                payment_status,
                payment_method,
                description,
                created_at
            ) VALUES (
                p_user_id,
                p_subscription_id,
                p_stripe_payment_intent_id,
                p_amount,
                COALESCE(p_currency, 'USD'),
                p_payment_status,
                'card',
                p_description,
                NOW()
            );

            SELECT 'success' as status, 'Payment recorded successfully' as message,
                   p_user_id as payment_user_id, p_amount as recorded_amount,
                   p_payment_status as recorded_status, LAST_INSERT_ID() as payment_record_id;
            COMMIT;
        END IF;
    END IF;
END//

-- ============================================================================
-- Procedure: ensure_user_has_subscription
-- Description: Ensure user has a default subscription (fallback for existing users)
-- ============================================================================
DROP PROCEDURE IF EXISTS ensure_user_has_subscription//

CREATE PROCEDURE ensure_user_has_subscription(
    IN p_user_id INT
)
BEGIN
    DECLARE subscription_exists INT DEFAULT 0;
    DECLARE free_plan_id INT DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT 'error' as status, 'Database error occurred while ensuring subscription' as message;
    END;

    START TRANSACTION;

    -- Check if user has any active subscription
    SELECT COUNT(*) INTO subscription_exists
    FROM user_subscriptions
    WHERE user_id = p_user_id AND status = 'active';

    IF subscription_exists = 0 THEN
        -- Get free plan ID if it exists
        SELECT id INTO free_plan_id
        FROM subscription_plans
        WHERE plan_type = 'free' AND is_active = TRUE
        LIMIT 1;

        IF free_plan_id IS NOT NULL THEN
            -- Create default free subscription
            INSERT INTO user_subscriptions (user_id, plan_id, status, created_at, updated_at)
            VALUES (p_user_id, free_plan_id, 'active', NOW(), NOW());

            SELECT 'success' as status, 'Default subscription created' as message,
                   p_user_id as user_id, free_plan_id as plan_id;
        ELSE
            -- No free plan available, user will operate without subscription
            SELECT 'success' as status, 'No free plan available, user has no subscription' as message,
                   p_user_id as user_id, NULL as plan_id;
        END IF;
    ELSE
        SELECT 'success' as status, 'Subscription already exists' as message,
               p_user_id as user_id, subscription_exists as existing_count;
    END IF;

    COMMIT;
END//

-- ============================================================================
-- Procedure: ensure_subscription_plans_exist
-- Description: Create default subscription plans if they don't exist
-- Used by: Application initialization
-- ============================================================================
DROP PROCEDURE IF EXISTS ensure_subscription_plans_exist//

CREATE PROCEDURE ensure_subscription_plans_exist()
BEGIN
    DECLARE plan_count INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT 'error' as status, 'Database error occurred while ensuring plans exist' as message;
    END;

    START TRANSACTION;

    -- Check if plans already exist
    SELECT COUNT(*) INTO plan_count FROM subscription_plans;

    IF plan_count = 0 THEN
        -- Create default plans
        INSERT INTO subscription_plans (plan_name, plan_type, price_per_month, price_per_product, max_products) 
        VALUES 
            ('Free Plan', 'free', 0.00, NULL, 2),
            ('Pay-as-you-go', 'pay_as_you_go', 0.00, 5.00, NULL),
            ('Unlimited Access', 'unlimited', 145.00, NULL, NULL);
        
        -- Create default AI Enhancement addon
        INSERT INTO subscription_addons (addon_name, addon_description, price_per_month) 
        VALUES ('AI Enhancement', 'Advanced AI failsafe tracking using ChatGPT, Claude AI & other models for 99% accuracy guarantee', 50.00);
        
        SELECT 'success' as status, 'Default plans created successfully' as message, 3 as plans_created;
    ELSE
        SELECT 'success' as status, 'Plans already exist' as message, plan_count as existing_plans;
    END IF;

    COMMIT;
END//

-- Reset delimiter
DELIMITER ;
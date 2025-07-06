-- ============================================================================
-- StockWatch Production Database Tables with SMS Support
-- ============================================================================

-- Use the stockwatch database
USE stockwatch;

-- ============================================================================
-- Users Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    newsletter_opt_in BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP NULL,
    
    -- Indexes for performance
    INDEX idx_email (email),
    INDEX idx_active (is_active),
    INDEX idx_created_at (created_at),
    INDEX idx_last_login (last_login_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Password Reset Tokens Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_token (token),
    INDEX idx_user_id (user_id),
    INDEX idx_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Email Verification Tokens Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_token (token),
    INDEX idx_user_id (user_id),
    INDEX idx_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- User Sessions Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    session_token VARCHAR(500) NOT NULL,
    refresh_token VARCHAR(500) NULL,
    ip_address VARCHAR(45) NULL,
    user_agent TEXT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_session_token (session_token),
    INDEX idx_expires_at (expires_at),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- User Activity Log Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_activity_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    activity_type VARCHAR(50) NOT NULL, -- 'login', 'logout', 'register', 'password_change', etc.
    ip_address VARCHAR(45) NULL,
    user_agent TEXT NULL,
    details JSON NULL,
    success BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_activity_type (activity_type),
    INDEX idx_created_at (created_at),
    INDEX idx_success (success)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Subscription Plans Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS subscription_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plan_name VARCHAR(100) NOT NULL,
    plan_type ENUM('free', 'pay_as_you_go', 'unlimited') NOT NULL,
    price_per_month DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    price_per_product DECIMAL(10,2) NULL,
    max_products INT NULL, -- NULL means unlimited
    stripe_price_id VARCHAR(255) NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_plan_type (plan_type),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Add-ons Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS subscription_addons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    addon_name VARCHAR(100) NOT NULL,
    addon_description TEXT NULL,
    price_per_month DECIMAL(10,2) NOT NULL,
    stripe_price_id VARCHAR(255) NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- User Subscriptions Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    plan_id INT NOT NULL,
    custom_product_limit INT NULL, -- For pay-as-you-go custom limits
    stripe_customer_id VARCHAR(255) NULL,
    stripe_subscription_id VARCHAR(255) NULL,
    stripe_session_id VARCHAR(255) NULL,
    status ENUM('active', 'cancelled', 'past_due', 'unpaid', 'paused') DEFAULT 'active',
    current_period_start TIMESTAMP NULL,
    current_period_end TIMESTAMP NULL,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES subscription_plans(id),
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_stripe_customer (stripe_customer_id),
    INDEX idx_stripe_subscription (stripe_subscription_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- User Subscription Add-ons Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_subscription_addons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    subscription_id INT NOT NULL,
    addon_id INT NOT NULL,
    stripe_subscription_item_id VARCHAR(255) NULL,
    status ENUM('active', 'cancelled') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (subscription_id) REFERENCES user_subscriptions(id) ON DELETE CASCADE,
    FOREIGN KEY (addon_id) REFERENCES subscription_addons(id),
    INDEX idx_subscription_id (subscription_id),
    INDEX idx_addon_id (addon_id),
    INDEX idx_status (status),
    UNIQUE KEY unique_subscription_addon (subscription_id, addon_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Payment History Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS payment_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subscription_id INT NULL,
    stripe_payment_intent_id VARCHAR(255) NULL,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    payment_status ENUM('succeeded', 'failed', 'pending', 'cancelled') NOT NULL,
    payment_method ENUM('card', 'bank_transfer', 'other') DEFAULT 'card',
    description TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (subscription_id) REFERENCES user_subscriptions(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_subscription_id (subscription_id),
    INDEX idx_payment_status (payment_status),
    INDEX idx_stripe_payment_intent (stripe_payment_intent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Product Usage Tracking Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS product_usage_tracking (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subscription_id INT NULL,
    products_used INT DEFAULT 0,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (subscription_id) REFERENCES user_subscriptions(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_period (period_start, period_end),
    UNIQUE KEY unique_user_period (user_id, period_start, period_end)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- User Products Table - WITH SMS SUPPORT
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    product_url VARCHAR(1000) NOT NULL,
    product_title VARCHAR(500) NULL,
    store_name VARCHAR(100) NULL,
    current_price DECIMAL(10,2) NULL,
    min_price_alert DECIMAL(10,2) NULL,
    max_price_alert DECIMAL(10,2) NULL,
    discord_webhook_url VARCHAR(500) NULL,
    sms_notifications_enabled BOOLEAN DEFAULT FALSE,  -- NEW: SMS notifications per product
    status ENUM('checking', 'in-stock', 'out-of-stock', 'error') DEFAULT 'checking',
    last_checked_at TIMESTAMP NULL,
    last_price_change TIMESTAMP NULL,
    alerts_sent INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_active (is_active),
    INDEX idx_last_checked (last_checked_at),
    INDEX idx_user_active (user_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Price History Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS product_price_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    status ENUM('in-stock', 'out-of-stock') NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (product_id) REFERENCES user_products(id) ON DELETE CASCADE,
    INDEX idx_product_id (product_id),
    INDEX idx_recorded_at (recorded_at),
    INDEX idx_product_date (product_id, recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- User Settings Table - WITH SMS SUPPORT
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    
    -- Notification Settings
    email_notifications BOOLEAN DEFAULT TRUE,
    discord_webhook_url VARCHAR(500) NULL,
    phone_number VARCHAR(20) NULL,               -- NEW: User's phone number for SMS
    sms_notifications BOOLEAN DEFAULT FALSE,     -- NEW: Global SMS notifications toggle
    notification_frequency ENUM('instant', 'hourly', 'daily') DEFAULT 'instant',
    
    -- Alert Settings
    price_drop_alerts BOOLEAN DEFAULT TRUE,
    restock_alerts BOOLEAN DEFAULT TRUE,
    price_increase_alerts BOOLEAN DEFAULT FALSE,
    
    -- Dashboard Settings
    dashboard_theme ENUM('light', 'dark', 'auto') DEFAULT 'light',
    items_per_page INT DEFAULT 10,
    default_currency VARCHAR(3) DEFAULT 'USD',
    
    -- Privacy Settings
    share_data BOOLEAN DEFAULT FALSE,
    public_profile BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_settings (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Product Alerts Log Table - WITH SMS SUPPORT
-- ============================================================================
CREATE TABLE IF NOT EXISTS product_alerts_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    user_id INT NOT NULL,
    alert_type ENUM('price_drop', 'restock', 'price_increase', 'out_of_stock') NOT NULL,
    old_price DECIMAL(10,2) NULL,
    new_price DECIMAL(10,2) NULL,
    old_status ENUM('in-stock', 'out-of-stock') NULL,
    new_status ENUM('in-stock', 'out-of-stock') NULL,
    notification_method ENUM('email', 'discord', 'sms', 'email_discord', 'email_sms', 'discord_sms', 'all') NOT NULL,  -- UPDATED: Added SMS options
    sent_successfully BOOLEAN DEFAULT FALSE,
    error_message TEXT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (product_id) REFERENCES user_products(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_product_id (product_id),
    INDEX idx_user_id (user_id),
    INDEX idx_alert_type (alert_type),
    INDEX idx_sent_at (sent_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Views for Easy Reporting
-- ============================================================================

-- Active subscriptions view
CREATE OR REPLACE VIEW active_subscriptions AS
SELECT 
    us.id as subscription_id,
    u.id as user_id,
    u.email,
    u.full_name,
    sp.plan_name,
    sp.plan_type,
    us.custom_product_limit,
    CASE 
        WHEN sp.plan_type = 'pay_as_you_go' THEN COALESCE(us.custom_product_limit, 0) * 5.00
        WHEN sp.plan_type = 'unlimited' THEN 145.00
        ELSE 0 
    END as monthly_revenue,
    us.current_period_start,
    us.current_period_end,
    us.created_at as subscription_started,
    (SELECT COUNT(*) FROM user_products up WHERE up.user_id = us.user_id AND up.is_active = TRUE) as products_tracked
FROM user_subscriptions us
JOIN users u ON us.user_id = u.id
JOIN subscription_plans sp ON us.plan_id = sp.id
WHERE us.status = 'active'
AND u.is_active = TRUE;

-- Revenue summary view
CREATE OR REPLACE VIEW revenue_summary AS
SELECT 
    DATE(ph.created_at) as revenue_date,
    COUNT(*) as transactions,
    SUM(CASE WHEN ph.payment_status = 'succeeded' THEN ph.amount ELSE 0 END) as successful_revenue,
    SUM(CASE WHEN ph.payment_status = 'failed' THEN ph.amount ELSE 0 END) as failed_revenue,
    COUNT(CASE WHEN ph.payment_status = 'succeeded' THEN 1 END) as successful_transactions,
    COUNT(CASE WHEN ph.payment_status = 'failed' THEN 1 END) as failed_transactions
FROM payment_history ph
WHERE ph.created_at >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
GROUP BY DATE(ph.created_at)
ORDER BY revenue_date DESC;
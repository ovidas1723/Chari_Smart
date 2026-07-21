PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS user (
    id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'donor', 'recipient', 'volunteer')),
    area VARCHAR(120),
    phone VARCHAR(30),
    organization_type VARCHAR(80),
    capacity_meals INTEGER DEFAULT 0,
    verified BOOLEAN DEFAULT 0,
    is_blocked BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS donation (
    id INTEGER NOT NULL PRIMARY KEY,
    food_name VARCHAR(150) NOT NULL,
    donor_type VARCHAR(50) NOT NULL,
    quantity_meals INTEGER NOT NULL,
    area VARCHAR(120) NOT NULL,
    pickup_address VARCHAR(255) NOT NULL,
    pickup_window_start DATETIME NOT NULL,
    pickup_window_end DATETIME NOT NULL,
    expire_at DATETIME NOT NULL,
    storage_note VARCHAR(255),
    description TEXT,
    verification_note VARCHAR(255),
    admin_note VARCHAR(255),
    status VARCHAR(30) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    donor_id INTEGER NOT NULL,
    FOREIGN KEY (donor_id) REFERENCES user(id)
);

CREATE TABLE IF NOT EXISTS food_request (
    id INTEGER NOT NULL PRIMARY KEY,
    beneficiary_group VARCHAR(150) NOT NULL,
    requested_food_type VARCHAR(150),
    quantity_needed INTEGER NOT NULL,
    area VARCHAR(120) NOT NULL,
    delivery_address VARCHAR(255) NOT NULL,
    needed_before DATETIME NOT NULL,
    message TEXT,
    priority VARCHAR(20) DEFAULT 'normal',
    admin_note VARCHAR(255),
    status VARCHAR(30) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    recipient_id INTEGER NOT NULL,
    FOREIGN KEY (recipient_id) REFERENCES user(id)
);

CREATE TABLE IF NOT EXISTS food_match (
    id INTEGER NOT NULL PRIMARY KEY,
    donation_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    volunteer_id INTEGER,
    meals_allocated INTEGER NOT NULL,
    match_score INTEGER DEFAULT 0,
    status VARCHAR(30) DEFAULT 'pending',
    pickup_confirmed_at DATETIME,
    delivered_at DATETIME,
    delivery_note TEXT,
    recipient_rating INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (donation_id) REFERENCES donation(id),
    FOREIGN KEY (request_id) REFERENCES food_request(id),
    FOREIGN KEY (volunteer_id) REFERENCES user(id)
);

CREATE TABLE IF NOT EXISTS notification (
    id INTEGER NOT NULL PRIMARY KEY,
    receiver_email VARCHAR(150) NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_donation_donor_id ON donation(donor_id);
CREATE INDEX IF NOT EXISTS idx_donation_status_area ON donation(status, area);
CREATE INDEX IF NOT EXISTS idx_food_request_recipient_id ON food_request(recipient_id);
CREATE INDEX IF NOT EXISTS idx_food_request_status_area ON food_request(status, area);
CREATE INDEX IF NOT EXISTS idx_food_match_donation_id ON food_match(donation_id);
CREATE INDEX IF NOT EXISTS idx_food_match_request_id ON food_match(request_id);
CREATE INDEX IF NOT EXISTS idx_food_match_volunteer_id ON food_match(volunteer_id);
CREATE INDEX IF NOT EXISTS idx_notification_receiver_email ON notification(receiver_email);


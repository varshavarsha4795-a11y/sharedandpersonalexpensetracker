-- USERS
INSERT INTO users (name, email, password, phone, created_at) VALUES
('BIRUNDHA', 'birundha@example.com', 'hashed_pass_1', '9790128006', '2026-01-05'),
('KIRUTHIGA', 'kiruthiga@example.com', 'hashed_pass_2', '9876543211', '2026-01-06'),
('KASHTHURI', 'kashthu@example.com', 'hashed_pass_3', '9876543212', '2026-01-07');

-- INCOME
INSERT INTO income (user_id, amount, source, date, description) VALUES
(1, 45000, 'Salary', '2026-07-01', 'Monthly salary credit'),
(1, 5000, 'Freelance', '2026-07-03', 'UI design project'),
(2, 38000, 'Salary', '2026-07-01', 'Monthly salary');

-- EXPENSE
INSERT INTO expense (user_id, amount, category, date, description) VALUES
(1, 1200, 'Food', '2026-07-02', 'Groceries'),
(1, 800, 'Transport', '2026-07-03', 'Cab fare'),
(2, 2500, 'Shopping', '2026-07-04', 'Clothes');

-- GROUPS
INSERT INTO groups (group_name, created_by, created_at) VALUES
('Goa Trip', 1, '2026-06-20'),
('Flat Rent Share', 2, '2026-06-25');

-- GROUP_MEMBERS
INSERT INTO group_members (group_id, user_id) VALUES
(1,1),
(1,2),
(1,3),
(2,2),
(2,3);

-- GROUP EXPENSE
INSERT INTO group_expense (group_id, paid_by, amount, description, date) VALUES
(1,1,900,'Dinner','2026-07-03'),
(1,2,600,'Movie','2026-07-04'),
(2,2,1500,'Groceries','2026-07-05');

-- SETTLEMENT
INSERT INTO settlement (group_id, payer_id, receiver_id, amount, date) VALUES
(1,2,1,300,'2026-07-05'),
(1,3,1,300,'2026-07-05'),
(2,3,2,750,'2026-07-05');

-- SETTINGS
INSERT INTO settings (user_id, currency, theme) VALUES
(1,'INR','Light'),
(2,'INR','Dark'),
(3,'USD','Light');


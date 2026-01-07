-- ============================================================================
-- PEACENAMES POC - DATABASE SCHEMA
-- ============================================================================
-- This schema implements the core data model for PeaceNames Level 1 POC.
-- 
-- KEY CONCEPTS:
-- 1. Users own files
-- 2. Files are tagged with bilingual tags
-- 3. Tags belong to dimensions (WHO, WHEN, WHAT, WHERE, HOW)
-- 4. C-Grid navigation = filtering by dimension values
--
-- For a typical software engineer: Think of this as a many-to-many 
-- relationship between files and tags, where tags are organized into
-- categories (dimensions) for structured browsing.
-- ============================================================================

-- Drop existing tables if they exist (for clean reinstall)
DROP DATABASE IF EXISTS peacenames;
CREATE DATABASE peacenames CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE peacenames;

-- ============================================================================
-- TABLE: users
-- ============================================================================
-- Represents a PeaceNames user. In the full system, this would connect to
-- the /NAME identity service and bilingual domain registration.
-- 
-- For POC: Simple user table to demonstrate file ownership.
-- ============================================================================
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Bilingual names: PeaceNames stores BOTH English and native language
    name_en VARCHAR(100) NOT NULL COMMENT 'English name (e.g., Sarah Lee)',
    name_zh VARCHAR(100) COMMENT 'Chinese/other language name (e.g., 李静)',
    
    -- In full system, this would be subdomain: sarah.lee.peacenames.com
    email VARCHAR(255) NOT NULL UNIQUE,
    
    -- Timestamps for audit trail (transparency is core to PeaceNames)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_email (email)
) ENGINE=InnoDB COMMENT='PeaceNames users - owners of personal archives';

-- ============================================================================
-- TABLE: dimensions
-- ============================================================================
-- Dimensions are the "axes" of the C-Grid. Liana defined 5 core dimensions
-- based on how human episodic memory works:
--   WHO   - People involved (Family, Work colleagues, Friends)
--   WHEN  - Time period (2023, 2024, Last Week)
--   WHAT  - Content type (Photos, Documents, Videos, Receipts)
--   WHERE - Location (Home, Paris, Office)
--   HOW   - Context/Activity (Vacation, Project, Birthday)
--
-- WHY DIMENSIONS MATTER:
-- Traditional folders force ONE path: /Family/2023/Vacation/Photos
-- C-Grid allows ANY combination: Family + 2023 + Vacation + Photos
-- You can reach the same file via multiple dimension combinations.
-- ============================================================================
CREATE TABLE dimensions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Dimension code (used in code, never changes)
    code VARCHAR(20) NOT NULL UNIQUE COMMENT 'WHO, WHEN, WHAT, WHERE, HOW',
    
    -- Bilingual display names
    name_en VARCHAR(50) NOT NULL COMMENT 'English label',
    name_zh VARCHAR(50) COMMENT 'Chinese label',
    
    -- Display order in UI
    display_order INT DEFAULT 0,
    
    -- Optional icon (from Liana s 25-icon system)
    icon_name VARCHAR(50) COMMENT 'Icon identifier for visual display',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='C-Grid dimensions (axes for navigation)';

-- ============================================================================
-- TABLE: tags
-- ============================================================================
-- Tags are the VALUES within each dimension. They form a hierarchy:
--   Dimension: WHO
--     └── Tag: Family (level 1)
--           └── Tag: Parents (level 2)
--           └── Tag: Children (level 2)
--     └── Tag: Work (level 1)
--           └── Tag: Team (level 2)
--
-- This hierarchical structure enables drill-down navigation:
-- Click WHO → see Family/Work/Friends → click Family → see Parents/Children
--
-- BILINGUAL DESIGN:
-- Every tag has both English and Chinese labels. The UI can switch
-- languages, but the underlying tag_id remains the same. This is how
-- PeaceNames achieves language-neutral semantic organization.
-- ============================================================================
CREATE TABLE tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Which dimension does this tag belong to?
    dimension_id INT NOT NULL,
    
    -- Bilingual labels - the user sees these
    name_en VARCHAR(100) NOT NULL COMMENT 'English tag name',
    name_zh VARCHAR(100) COMMENT 'Chinese tag name',
    
    -- Hierarchy: NULL means top-level tag, otherwise points to parent
    parent_id INT DEFAULT NULL COMMENT 'Parent tag for hierarchy (NULL = root)',
    
    -- Level in hierarchy (1 = top level, 2 = second level, etc.)
    -- Liana mentioned human brains work well with ~6 levels max
    level INT DEFAULT 1 COMMENT 'Depth in tag hierarchy',
    
    -- Optional icon (from Liana s 25-icon system)
    icon_url VARCHAR(255) COMMENT 'URL or path to icon image',
    
    -- Display order within parent
    display_order INT DEFAULT 0,
    
    -- Is this tag active? (soft delete support)
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (dimension_id) REFERENCES dimensions(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES tags(id) ON DELETE SET NULL,
    
    INDEX idx_dimension (dimension_id),
    INDEX idx_parent (parent_id),
    INDEX idx_active (is_active)
) ENGINE=InnoDB COMMENT='Bilingual tags organized by dimension';

-- ============================================================================
-- TABLE: files
-- ============================================================================
-- User-uploaded files in the personal archive. In the full PeaceNames
-- system, this would be stored in the /EXP (Experience) server of the
-- quartet.
--
-- WHAT GETS STORED:
-- - Photos, documents, PDFs, receipts, videos, voice notes
-- - Basically anything you'd put in Google Drive or Dropbox
-- - The difference: organized by semantic tags, not folders
-- ============================================================================
CREATE TABLE files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Who owns this file?
    user_id INT NOT NULL,
    
    -- Original filename (preserved for user reference)
    original_filename VARCHAR(255) NOT NULL COMMENT 'Name when uploaded',
    
    -- Where it is stored on disk (internal path)
    storage_path VARCHAR(500) NOT NULL COMMENT 'Server file path',
    
    -- MIME type for proper display/download
    mime_type VARCHAR(100) COMMENT 'e.g., image/jpeg, application/pdf',
    
    -- File size in bytes (for quota management)
    size_bytes BIGINT DEFAULT 0,
    
    -- Optional user description
    description TEXT COMMENT 'User notes about this file',
    
    -- Audit timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    INDEX idx_user (user_id),
    INDEX idx_created (created_at)
) ENGINE=InnoDB COMMENT='User files in the personal archive';

-- ============================================================================
-- TABLE: file_tags (Junction Table)
-- ============================================================================
-- This is the HEART of the C-Grid system. It connects files to tags.
-- 
-- A single file can have MULTIPLE tags from MULTIPLE dimensions:
--   photo.jpg:
--     WHO: Family
--     WHEN: 2023
--     WHAT: Photo
--     WHERE: Paris
--     HOW: Vacation
--
-- C-GRID NAVIGATION WORKS BY:
-- 1. User clicks dimension (e.g., WHO)
-- 2. System shows all tags in that dimension
-- 3. User clicks tag (e.g., Family)
-- 4. System filters to files with that tag
-- 5. User clicks another dimension (e.g., WHEN)
-- 6. System shows remaining options
-- 7. User clicks tag (e.g., 2023)
-- 8. System narrows further
-- 
-- After 3-4 clicks, user finds their file!
-- ============================================================================
CREATE TABLE file_tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    file_id INT NOT NULL,
    tag_id INT NOT NULL,
    
    -- When was this tag assigned? (audit trail)
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Who assigned it? (for future: could be user or AI suggestion)
    assigned_by INT COMMENT 'User who assigned this tag',
    
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE SET NULL,
    
    -- Prevent duplicate tag assignments
    UNIQUE KEY unique_file_tag (file_id, tag_id),
    
    INDEX idx_file (file_id),
    INDEX idx_tag (tag_id)
) ENGINE=InnoDB COMMENT='Links files to tags (C-Grid core)';

-- ============================================================================
-- TABLE: cgrid_sessions (Optional - for tracking navigation)
-- ============================================================================
-- Tracks user navigation through the C-Grid. This helps:
-- 1. Remember where user left off
-- 2. Analytics on how people navigate
-- 3. Future: ML to suggest tags based on navigation patterns
-- ============================================================================
CREATE TABLE cgrid_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    user_id INT NOT NULL,
    
    -- Current filter state as JSON
    -- Example: {"WHO": [1], "WHEN": [5, 6], "WHAT": [10]}
    -- (tag IDs selected in each dimension)
    current_filters JSON COMMENT 'Current dimension filters',
    
    -- Timestamps
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    INDEX idx_user (user_id)
) ENGINE=InnoDB COMMENT='User C-Grid navigation sessions';

-- ============================================================================
-- SEED DATA: Dimensions
-- ============================================================================
-- These are the 5 core dimensions from Liana's design.
-- Based on human episodic memory: Who, When, What, Where, How
-- ============================================================================
INSERT INTO dimensions (code, name_en, name_zh, display_order, icon_name) VALUES
('WHO',   'Who',   '谁',   1, 'person'),
('WHEN',  'When',  '何时', 2, 'calendar'),
('WHAT',  'What',  '什么', 3, 'file'),
('WHERE', 'Where', '哪里', 4, 'location'),
('HOW',   'How',   '如何', 5, 'activity');

-- ============================================================================
-- SEED DATA: Sample Tags
-- ============================================================================
-- These are example tags to populate the POC. In the full system,
-- Liana's tri-lingual tag table with 25 top-level icons would be used.
--
-- HIERARCHY EXAMPLE:
-- WHO (dimension)
--   └── Family (level 1 tag)
--         └── Parents (level 2 tag)
--         └── Children (level 2 tag)
--         └── Extended Family (level 2 tag)
-- ============================================================================

-- WHO dimension tags (dimension_id = 1)
INSERT INTO tags (dimension_id, name_en, name_zh, parent_id, level, display_order) VALUES
-- Level 1 (top-level)
(1, 'Family', '家人', NULL, 1, 1),
(1, 'Work', '工作', NULL, 1, 2),
(1, 'Friends', '朋友', NULL, 1, 3),
(1, 'Self', '自己', NULL, 1, 4);

-- Level 2 under Family (parent_id = 1)
INSERT INTO tags (dimension_id, name_en, name_zh, parent_id, level, display_order) VALUES
(1, 'Parents', '父母', 1, 2, 1),
(1, 'Children', '孩子', 1, 2, 2),
(1, 'Spouse', '配偶', 1, 2, 3),
(1, 'Extended Family', '亲戚', 1, 2, 4);

-- Level 2 under Work (parent_id = 2)
INSERT INTO tags (dimension_id, name_en, name_zh, parent_id, level, display_order) VALUES
(1, 'Team', '团队', 2, 2, 1),
(1, 'Clients', '客户', 2, 2, 2),
(1, 'Management', '管理层', 2, 2, 3);

-- WHEN dimension tags (dimension_id = 2)
INSERT INTO tags (dimension_id, name_en, name_zh, parent_id, level, display_order) VALUES
(2, '2024', '2024年', NULL, 1, 1),
(2, '2023', '2023年', NULL, 1, 2),
(2, '2022', '2022年', NULL, 1, 3),
(2, '2021', '2021年', NULL, 1, 4),
(2, 'Older', '更早', NULL, 1, 5);

-- Quarters under 2024 (parent_id = 12)
INSERT INTO tags (dimension_id, name_en, name_zh, parent_id, level, display_order) VALUES
(2, 'Q1 2024', '2024第一季度', 12, 2, 1),
(2, 'Q2 2024', '2024第二季度', 12, 2, 2),
(2, 'Q3 2024', '2024第三季度', 12, 2, 3),
(2, 'Q4 2024', '2024第四季度', 12, 2, 4);

-- WHAT dimension tags (dimension_id = 3)
INSERT INTO tags (dimension_id, name_en, name_zh, parent_id, level, display_order) VALUES
(3, 'Photos', '照片', NULL, 1, 1),
(3, 'Documents', '文档', NULL, 1, 2),
(3, 'Videos', '视频', NULL, 1, 3),
(3, 'Audio', '音频', NULL, 1, 4),
(3, 'Receipts', '收据', NULL, 1, 5),
(3, 'Notes', '笔记', NULL, 1, 6);

-- Sub-types under Photos (parent_id = 21)
INSERT INTO tags (dimension_id, name_en, name_zh, parent_id, level, display_order) VALUES
(3, 'Portraits', '人像', 21, 2, 1),
(3, 'Landscapes', '风景', 21, 2, 2),
(3, 'Screenshots', '截图', 21, 2, 3),
(3, 'Scanned Docs', '扫描件', 21, 2, 4);

-- Sub-types under Documents (parent_id = 22)
INSERT INTO tags (dimension_id, name_en, name_zh, parent_id, level, display_order) VALUES
(3, 'Reports', '报告', 22, 2, 1),
(3, 'Contracts', '合同', 22, 2, 2),
(3, 'Letters', '信件', 22, 2, 3),
(3, 'Presentations', '演示文稿', 22, 2, 4);

-- WHERE dimension tags (dimension_id = 4)
INSERT INTO tags (dimension_id, name_en, name_zh, parent_id, level, display_order) VALUES
(4, 'Home', '家', NULL, 1, 1),
(4, 'Office', '办公室', NULL, 1, 2),
(4, 'Travel', '旅行', NULL, 1, 3),
(4, 'School', '学校', NULL, 1, 4);

-- Travel destinations (parent_id = 37)
INSERT INTO tags (dimension_id, name_en, name_zh, parent_id, level, display_order) VALUES
(4, 'USA', '美国', 37, 2, 1),
(4, 'Europe', '欧洲', 37, 2, 2),
(4, 'Asia', '亚洲', 37, 2, 3),
(4, 'Other', '其他', 37, 2, 4);

-- HOW dimension tags (dimension_id = 5)
INSERT INTO tags (dimension_id, name_en, name_zh, parent_id, level, display_order) VALUES
(5, 'Vacation', '度假', NULL, 1, 1),
(5, 'Project', '项目', NULL, 1, 2),
(5, 'Celebration', '庆祝', NULL, 1, 3),
(5, 'Daily Life', '日常', NULL, 1, 4),
(5, 'Learning', '学习', NULL, 1, 5);

-- Celebration types (parent_id = 45)
INSERT INTO tags (dimension_id, name_en, name_zh, parent_id, level, display_order) VALUES
(5, 'Birthday', '生日', 45, 2, 1),
(5, 'Wedding', '婚礼', 45, 2, 2),
(5, 'Graduation', '毕业', 45, 2, 3),
(5, 'Holiday', '节日', 45, 2, 4);

-- ============================================================================
-- SEED DATA: Sample User
-- ============================================================================
INSERT INTO users (name_en, name_zh, email) VALUES
('Sarah Lee', '李静', 'sarah.lee@example.com'),
('Demo User', '演示用户', 'demo@peacenames.com');

-- ============================================================================
-- SEED DATA: Sample Files (for demonstration)
-- ============================================================================
INSERT INTO files (user_id, original_filename, storage_path, mime_type, size_bytes, description) VALUES
(1, 'family_vacation_paris.jpg', '/uploads/1/family_vacation_paris.jpg', 'image/jpeg', 2500000, 'Family trip to Paris, summer 2023'),
(1, 'birthday_party_2023.jpg', '/uploads/1/birthday_party_2023.jpg', 'image/jpeg', 1800000, 'Mom''s 60th birthday celebration'),
(1, 'quarterly_report_q3.pdf', '/uploads/1/quarterly_report_q3.pdf', 'application/pdf', 450000, 'Q3 2023 sales report'),
(1, 'house_purchase_contract.pdf', '/uploads/1/house_purchase_contract.pdf', 'application/pdf', 890000, 'House purchase agreement 2022'),
(1, 'kids_school_play.mp4', '/uploads/1/kids_school_play.mp4', 'video/mp4', 125000000, 'Children''s school play recording'),
(1, 'travel_receipt_hotel.pdf', '/uploads/1/travel_receipt_hotel.pdf', 'application/pdf', 150000, 'Hotel receipt from Paris trip'),
(1, 'wedding_anniversary.jpg', '/uploads/1/wedding_anniversary.jpg', 'image/jpeg', 3200000, '10th wedding anniversary dinner'),
(1, 'project_presentation.pptx', '/uploads/1/project_presentation.pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 5600000, 'Client project final presentation'),
(2, 'demo_photo_1.jpg', '/uploads/2/demo_photo_1.jpg', 'image/jpeg', 1000000, 'Demo photo for testing'),
(2, 'demo_document.pdf', '/uploads/2/demo_document.pdf', 'application/pdf', 200000, 'Demo document for testing');

-- ============================================================================
-- SEED DATA: File-Tag Assignments
-- ============================================================================
-- This is where the magic happens! Each file gets multiple tags.
-- 
-- EXAMPLE: family_vacation_paris.jpg (file_id = 1)
--   WHO: Family (tag_id = 1)
--   WHEN: 2023 (tag_id = 13)
--   WHAT: Photos (tag_id = 21)
--   WHERE: Travel > Europe (tag_id = 40)
--   HOW: Vacation (tag_id = 43)
--
-- Now this photo can be found by ANY of these paths:
--   Family → 2023 → Photos
--   Travel → Europe → Photos
--   Vacation → 2023 → Family
--   etc.
-- ============================================================================

-- File 1: family_vacation_paris.jpg
INSERT INTO file_tags (file_id, tag_id, assigned_by) VALUES
(1, 1, 1),   -- WHO: Family
(1, 13, 1), -- WHEN: 2023
(1, 21, 1), -- WHAT: Photos
(1, 40, 1), -- WHERE: Europe (under Travel)
(1, 43, 1); -- HOW: Vacation

-- File 2: birthday_party_2023.jpg
INSERT INTO file_tags (file_id, tag_id, assigned_by) VALUES
(2, 1, 1),   -- WHO: Family
(2, 5, 1),  -- WHO: Parents (sub-tag)
(2, 13, 1), -- WHEN: 2023
(2, 21, 1), -- WHAT: Photos
(2, 35, 1), -- WHERE: Home
(2, 45, 1), -- HOW: Celebration
(2, 48, 1); -- HOW: Birthday (sub-tag)

-- File 3: quarterly_report_q3.pdf
INSERT INTO file_tags (file_id, tag_id, assigned_by) VALUES
(3, 2, 1),   -- WHO: Work
(3, 13, 1), -- WHEN: 2023
(3, 22, 1), -- WHAT: Documents
(3, 31, 1), -- WHAT: Reports (sub-tag)
(3, 36, 1), -- WHERE: Office
(3, 44, 1); -- HOW: Project

-- File 4: house_purchase_contract.pdf
INSERT INTO file_tags (file_id, tag_id, assigned_by) VALUES
(4, 4, 1),   -- WHO: Self
(4, 14, 1), -- WHEN: 2022
(4, 22, 1), -- WHAT: Documents
(4, 32, 1), -- WHAT: Contracts (sub-tag)
(4, 35, 1), -- WHERE: Home
(4, 46, 1); -- HOW: Daily Life

-- File 5: kids_school_play.mp4
INSERT INTO file_tags (file_id, tag_id, assigned_by) VALUES
(5, 1, 1),   -- WHO: Family
(5, 6, 1),  -- WHO: Children (sub-tag)
(5, 13, 1), -- WHEN: 2023
(5, 23, 1), -- WHAT: Videos
(5, 38, 1), -- WHERE: School
(5, 45, 1); -- HOW: Celebration

-- File 6: travel_receipt_hotel.pdf
INSERT INTO file_tags (file_id, tag_id, assigned_by) VALUES
(6, 4, 1),   -- WHO: Self
(6, 13, 1), -- WHEN: 2023
(6, 25, 1), -- WHAT: Receipts
(6, 40, 1), -- WHERE: Europe
(6, 43, 1); -- HOW: Vacation

-- File 7: wedding_anniversary.jpg
INSERT INTO file_tags (file_id, tag_id, assigned_by) VALUES
(7, 1, 1),   -- WHO: Family
(7, 7, 1),  -- WHO: Spouse (sub-tag)
(7, 12, 1), -- WHEN: 2024
(7, 21, 1), -- WHAT: Photos
(7, 35, 1), -- WHERE: Home
(7, 45, 1); -- HOW: Celebration

-- File 8: project_presentation.pptx
INSERT INTO file_tags (file_id, tag_id, assigned_by) VALUES
(8, 2, 1),   -- WHO: Work
(8, 10, 1), -- WHO: Clients (sub-tag)
(8, 12, 1), -- WHEN: 2024
(8, 22, 1), -- WHAT: Documents
(8, 34, 1), -- WHAT: Presentations (sub-tag)
(8, 36, 1), -- WHERE: Office
(8, 44, 1); -- HOW: Project

-- Demo user files
INSERT INTO file_tags (file_id, tag_id, assigned_by) VALUES
(9, 4, 2),   -- WHO: Self
(9, 12, 2), -- WHEN: 2024
(9, 21, 2), -- WHAT: Photos
(10, 4, 2), -- WHO: Self
(10, 12, 2),-- WHEN: 2024
(10, 22, 2);-- WHAT: Documents

-- ============================================================================
-- USEFUL VIEWS (for easier querying)
-- ============================================================================

-- View: Files with their tags (denormalized for easy display)
CREATE VIEW v_file_details AS
SELECT 
    f.id AS file_id,
    f.user_id,
    f.original_filename,
    f.mime_type,
    f.size_bytes,
    f.description,
    f.created_at,
    u.name_en AS owner_name_en,
    u.name_zh AS owner_name_zh
FROM files f
JOIN users u ON f.user_id = u.id;

-- View: Tag counts per dimension (for C-Grid display)
CREATE VIEW v_dimension_tag_counts AS
SELECT 
    d.id AS dimension_id,
    d.code AS dimension_code,
    d.name_en AS dimension_name_en,
    d.name_zh AS dimension_name_zh,
    COUNT(t.id) AS tag_count
FROM dimensions d
LEFT JOIN tags t ON d.id = t.dimension_id AND t.is_active = TRUE
GROUP BY d.id, d.code, d.name_en, d.name_zh;

-- View: File counts per tag (for showing numbers in C-Grid)
CREATE VIEW v_tag_file_counts AS
SELECT 
    t.id AS tag_id,
    t.name_en,
    t.name_zh,
    t.dimension_id,
    d.code AS dimension_code,
    COUNT(ft.file_id) AS file_count
FROM tags t
JOIN dimensions d ON t.dimension_id = d.id
LEFT JOIN file_tags ft ON t.id = ft.tag_id
WHERE t.is_active = TRUE
GROUP BY t.id, t.name_en, t.name_zh, t.dimension_id, d.code;

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================
-- These indexes optimize the common C-Grid queries:
-- 1. Get all tags in a dimension
-- 2. Get all files with a specific tag
-- 3. Get all tags for a specific file
-- 4. Filter files by multiple tags (intersection)
-- ============================================================================

-- Already created via FOREIGN KEY and explicit INDEX statements above
-- Additional composite indexes for common queries:

CREATE INDEX idx_tags_dimension_active ON tags(dimension_id, is_active);
CREATE INDEX idx_tags_parent_level ON tags(parent_id, level);

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
-- To use this schema:
-- 1. mysql -u root -p < schema.sql
-- 2. Or in MySQL client: source /path/to/schema.sql
-- ============================================================================

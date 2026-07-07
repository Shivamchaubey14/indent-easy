-- Connect to database
USE shwetdhara_db;

-- ============================================
-- 1. CUSTOM USER TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_customuser` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `password` varchar(128) NOT NULL,
    `last_login` datetime(6) NULL,
    `is_superuser` tinyint(1) NOT NULL,
    `first_name` varchar(150) NOT NULL,
    `last_name` varchar(150) NOT NULL,
    `is_staff` tinyint(1) NOT NULL,
    `is_active` tinyint(1) NOT NULL,
    `date_joined` datetime(6) NOT NULL,
    `email` varchar(254) NOT NULL UNIQUE,
    `location` varchar(255) NOT NULL,
    `plant` varchar(50) NULL,
    `is_hod` tinyint(1) NOT NULL DEFAULT 0,
    `is_purchase` tinyint(1) NOT NULL DEFAULT 0,
    `is_finance` tinyint(1) NOT NULL DEFAULT 0,
    `is_logistic` tinyint(1) NOT NULL DEFAULT 0,
    `employee_code` varchar(255) NOT NULL,
    `department` varchar(255) NOT NULL,
    `address` longtext NULL,
    `delivery_point_code` varchar(255) NULL UNIQUE,
    `signature` varchar(100) NULL,
    `mohar` varchar(100) NULL,
    
    INDEX `idx_customuser_email` (`email`),
    INDEX `idx_customuser_location` (`location`),
    INDEX `idx_customuser_employee_code` (`employee_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 2. PRODUCT MAPPING
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_productmapping` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `system` varchar(20) NOT NULL,
    `product_name` varchar(255) NOT NULL,
    `product_code` varchar(100) NULL,
    `description` longtext NULL,
    `uom` varchar(50) NULL,
    `size` varchar(50) NULL,
    `material_type` varchar(255) NULL,
    `is_active` tinyint(1) NOT NULL DEFAULT 1,
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    
    UNIQUE KEY `unique_system_product` (`system`, `product_name`),
    INDEX `idx_productmapping_system` (`system`),
    INDEX `idx_productmapping_product_name` (`product_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 3. PRODUCT MAPPING GROUP
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_productmappinggroup` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `name` varchar(255) NOT NULL UNIQUE,
    `description` longtext NULL,
    `is_active` tinyint(1) NOT NULL DEFAULT 1,
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 4. PRODUCT MAPPING RELATION
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_productmappingrelation` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `group_id` bigint NOT NULL,
    `product_mapping_id` bigint NOT NULL,
    `is_primary` tinyint(1) NOT NULL DEFAULT 0,
    `created_at` datetime(6) NOT NULL,
    
    UNIQUE KEY `unique_group_product` (`group_id`, `product_mapping_id`),
    FOREIGN KEY (`group_id`) REFERENCES `main_app_productmappinggroup` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`product_mapping_id`) REFERENCES `main_app_productmapping` (`id`) ON DELETE CASCADE,
    INDEX `idx_productmappingrelation_group` (`group_id`),
    INDEX `idx_productmappingrelation_product` (`product_mapping_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 5. VENDOR
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_vendor` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `name` varchar(255) NOT NULL UNIQUE,
    `email` longtext NULL,
    `address` longtext NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 6. PRODUCT
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_product` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `product_code` varchar(255) NULL UNIQUE,
    `name` varchar(255) NOT NULL UNIQUE,
    `size` varchar(50) NULL,
    `uom` varchar(50) NULL,
    `material_type` varchar(255) NULL,
    `category` varchar(50) NULL,
    `price` decimal(10,2) NOT NULL DEFAULT 0.00,
    `is_active` tinyint(1) NOT NULL DEFAULT 1,
    `hod_id` bigint NULL,
    
    CONSTRAINT `unique_product_name_size` UNIQUE (`name`, `size`),
    FOREIGN KEY (`hod_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    INDEX `idx_product_name` (`name`),
    INDEX `idx_product_category` (`category`),
    INDEX `idx_product_hod` (`hod_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 7. PRODUCT VENDOR (Many-to-Many)
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_productvendor` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `product_id` bigint NOT NULL,
    `vendor_id` bigint NOT NULL,
    `added_at` datetime(6) NOT NULL,
    
    UNIQUE KEY `unique_product_vendor` (`product_id`, `vendor_id`),
    FOREIGN KEY (`product_id`) REFERENCES `main_app_product` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`vendor_id`) REFERENCES `main_app_vendor` (`id`) ON DELETE CASCADE,
    INDEX `idx_productvendor_product` (`product_id`),
    INDEX `idx_productvendor_vendor` (`vendor_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 8. BMC OR MCC
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_bmcorMCC` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `name` varchar(100) NOT NULL UNIQUE,
    `plant` varchar(50) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 9. MPP WITH CODE
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_mppwithcode` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `mpp_transaction_code` varchar(100) NULL UNIQUE,
    `bmc_or_mcc_id` bigint NOT NULL,
    `name_with_code` varchar(100) NOT NULL,
    `sahayak_mobile_number` varchar(15) NULL,
    `cycle` varchar(10) NULL,
    `location` varchar(255) NULL,
    `status` varchar(20) NOT NULL,
    `created_at` datetime(6) NULL,
    `updated_at` datetime(6) NULL,
    
    UNIQUE KEY `unique_bmc_name_code` (`bmc_or_mcc_id`, `name_with_code`, `mpp_transaction_code`),
    FOREIGN KEY (`bmc_or_mcc_id`) REFERENCES `main_app_bmcorMCC` (`id`) ON DELETE CASCADE,
    INDEX `idx_mppwithcode_bmc` (`bmc_or_mcc_id`),
    INDEX `idx_mppwithcode_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 10. MONTHLY CYCLE
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_monthlycycle` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `month` varchar(20) NOT NULL,
    `year` int unsigned NOT NULL,
    `name` varchar(100) NOT NULL,
    `description` longtext NULL,
    `is_active` tinyint(1) NOT NULL DEFAULT 1,
    `created_by_id` bigint NOT NULL,
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    
    UNIQUE KEY `unique_month_year` (`month`, `year`),
    FOREIGN KEY (`created_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    INDEX `idx_monthlycycle_created_by` (`created_by_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 11. CYCLE
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_cycle` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `monthly_cycle_id` bigint NOT NULL,
    `name` varchar(50) NOT NULL,
    `sap_number` varchar(50) NULL,
    `cycle_number` int unsigned NOT NULL,
    `start_date` date NOT NULL,
    `end_date` date NOT NULL,
    `description` longtext NULL,
    `is_active` tinyint(1) NOT NULL DEFAULT 1,
    
    UNIQUE KEY `unique_monthly_cycle_number` (`monthly_cycle_id`, `cycle_number`),
    FOREIGN KEY (`monthly_cycle_id`) REFERENCES `main_app_monthlycycle` (`id`) ON DELETE CASCADE,
    INDEX `idx_cycle_monthly` (`monthly_cycle_id`),
    INDEX `idx_cycle_dates` (`start_date`, `end_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 12. ADVANCE SALE
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_advancesale` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `bmc_or_mcc` varchar(50) NULL,
    `mpp_with_code` varchar(50) NULL,
    `uom` varchar(50) NULL,
    `stock_item` varchar(255) NULL,
    `quantity` int unsigned NULL,
    `dispatched_at` datetime(6) NOT NULL,
    `dispatched_by_id` bigint NOT NULL,
    `pod_uploaded` tinyint(1) NOT NULL DEFAULT 0,
    `pod_uploaded_at` datetime(6) NULL,
    `pod_file` varchar(500) NULL,
    `unique_code` varchar(50) NULL,
    `pdf_file` varchar(100) NULL,
    `pdf_generated` tinyint(1) NOT NULL DEFAULT 0,
    `cycle_id` bigint NULL,
    `sale_date` date NOT NULL,
    `template_entry_id` bigint NULL,
    
    FOREIGN KEY (`dispatched_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`cycle_id`) REFERENCES `main_app_cycle` (`id`) ON DELETE SET NULL,
    INDEX `idx_advancesale_unique_code` (`unique_code`),
    INDEX `idx_advancesale_cycle` (`cycle_id`),
    INDEX `idx_advancesale_dispatched_by` (`dispatched_by_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 13. SALE TEMPLATE CONFIG
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_saletemplateconfig` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `cycle_id` bigint NOT NULL,
    `is_active` tinyint(1) NOT NULL DEFAULT 1,
    `created_at` datetime(6) NOT NULL,
    
    FOREIGN KEY (`cycle_id`) REFERENCES `main_app_cycle` (`id`) ON DELETE CASCADE,
    INDEX `idx_saletemplateconfig_cycle` (`cycle_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 14. SALE TEMPLATE ENTRY
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_saletemplateentry` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `config_id` bigint NOT NULL,
    `location` varchar(255) NOT NULL,
    `mpp` varchar(255) NOT NULL,
    `product_name` varchar(255) NOT NULL,
    `advance_sale_quantity` int unsigned NOT NULL DEFAULT 0,
    `filled_quantity` int unsigned NOT NULL DEFAULT 0,
    `status` varchar(20) NOT NULL DEFAULT 'NOT_SOLD',
    `uploaded_by_id` bigint NULL,
    `uploaded_at` datetime(6) NOT NULL,
    
    UNIQUE KEY `unique_config_location_mpp_product` (`config_id`, `location`, `mpp`, `product_name`),
    FOREIGN KEY (`config_id`) REFERENCES `main_app_saletemplateconfig` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`uploaded_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE SET NULL,
    INDEX `idx_saletemplateentry_config` (`config_id`),
    INDEX `idx_saletemplateentry_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 15. SALE UPLOAD HISTORY
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_saleuploadhistory` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `config_id` bigint NOT NULL,
    `file_name` varchar(255) NOT NULL,
    `uploaded_by_id` bigint NOT NULL,
    `total_records` int unsigned NOT NULL DEFAULT 0,
    `success_count` int unsigned NOT NULL DEFAULT 0,
    `error_count` int unsigned NOT NULL DEFAULT 0,
    `uploaded_at` datetime(6) NOT NULL,
    
    FOREIGN KEY (`config_id`) REFERENCES `main_app_saletemplateconfig` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`uploaded_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    INDEX `idx_saleuploadhistory_config` (`config_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 16. PURCHASE REQUISITION
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_purchaserequisition` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `created_by_id` bigint NULL,
    `requisition_number` varchar(10) NOT NULL DEFAULT '',
    `date_of_request` date NOT NULL,
    `time_of_request` time(6) NOT NULL,
    `department` varchar(100) NULL,
    `employee_name` varchar(245) NOT NULL DEFAULT 'EMPLOYEE',
    `employee_code` varchar(50) NOT NULL,
    `location` varchar(100) NOT NULL DEFAULT 'LOCATION NOT PROVIDED',
    `uom` varchar(20) NOT NULL,
    `stock_item` varchar(255) NOT NULL,
    `quantity` int NOT NULL,
    `expected_delivery_date` date NULL,
    `remark` longtext NULL,
    `status` varchar(250) NOT NULL DEFAULT 'INDENT RAISED',
    `created_at` datetime(6) NOT NULL,
    `po_number` varchar(200) NULL,
    `grn_done` tinyint(1) NOT NULL DEFAULT 0,
    `send_grn_mail` tinyint(1) NOT NULL DEFAULT 0,
    `grn_cancelled` tinyint(1) NOT NULL DEFAULT 0,
    `grn_cancelled_at` datetime(6) NULL,
    `grn_cancelled_by_id` bigint NULL,
    
    FOREIGN KEY (`created_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE SET NULL,
    FOREIGN KEY (`grn_cancelled_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE SET NULL,
    INDEX `idx_purchaserequisition_number` (`requisition_number`),
    INDEX `idx_purchaserequisition_status` (`status`),
    INDEX `idx_purchaserequisition_created_by` (`created_by_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 17. HOD APPROVAL
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_hodapproval` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `requisition_id` bigint NOT NULL,
    `status` varchar(250) NOT NULL DEFAULT 'PENDING',
    `approved_by_id` bigint NULL,
    `approval_date` datetime(6) NULL,
    
    FOREIGN KEY (`requisition_id`) REFERENCES `main_app_purchaserequisition` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`approved_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE SET NULL,
    INDEX `idx_hodapproval_requisition` (`requisition_id`),
    INDEX `idx_hodapproval_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 18. PURCHASE DEPARTMENT
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_purchasedepartment` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `requisition_id` bigint NOT NULL,
    `po_number` varchar(255) NULL UNIQUE,
    `po_generated_by_id` bigint NULL,
    `po_generation_date` datetime(6) NULL,
    `party_name` varchar(255) NULL,
    `email` varchar(255) NULL,
    `remarks_of` varchar(254) NULL,
    `mail_sent` tinyint(1) NOT NULL DEFAULT 0,
    
    FOREIGN KEY (`requisition_id`) REFERENCES `main_app_purchaserequisition` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`po_generated_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE SET NULL,
    INDEX `idx_purchasedepartment_requisition` (`requisition_id`),
    INDEX `idx_purchasedepartment_po_number` (`po_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 19. LOGISTIC DEPARTMENT
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_logisticdepartment` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `requested_by_id` bigint NULL,
    `requisition_id` bigint NULL,
    `to_location` varchar(100) NOT NULL,
    `from_location` varchar(100) NOT NULL,
    `stock_item` varchar(255) NOT NULL,
    `quantity` int NOT NULL,
    `created_at` datetime(6) NOT NULL,
    `stn_number` varchar(30) NULL,
    `mail_sent` tinyint(1) NOT NULL DEFAULT 0,
    
    FOREIGN KEY (`requested_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE SET NULL,
    FOREIGN KEY (`requisition_id`) REFERENCES `main_app_purchaserequisition` (`id`) ON DELETE SET NULL,
    INDEX `idx_logisticdepartment_requisition` (`requisition_id`),
    INDEX `idx_logisticdepartment_stn` (`stn_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 20. DO GRN
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_dorgn` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `grn_number` varchar(50) NULL,
    `requisition_number` varchar(50) NULL,
    `po_number` varchar(50) NOT NULL,
    `date_of_receipt` date NOT NULL,
    `time_of_receipt` time(6) NOT NULL,
    `location` varchar(255) NOT NULL,
    `chaalan_number` varchar(255) NULL,
    `chaalan_file` varchar(100) NULL,
    `invoice_file` varchar(100) NULL,
    `employee_name` varchar(255) NOT NULL,
    `employee_code` varchar(255) NOT NULL,
    `uom` varchar(50) NOT NULL,
    `stock_item` varchar(255) NOT NULL,
    `quantity_ordered` int unsigned NOT NULL,
    `quantity_received` int unsigned NOT NULL,
    `quantity_rejected` int unsigned NOT NULL DEFAULT 0,
    `remarks` longtext NULL,
    `approval_file` varchar(100) NULL,
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    
    INDEX `idx_dorgn_po_number` (`po_number`),
    INDEX `idx_dorgn_grn_number` (`grn_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 21. DO GRN AGAINST STN
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_dorgnagainststn` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `stn_number` varchar(50) NOT NULL,
    `grn_number` varchar(50) NULL,
    `stn_date` date NOT NULL,
    `stn_file` varchar(100) NULL,
    `eway_bill_file` varchar(100) NULL,
    `employee_name` varchar(255) NOT NULL,
    `employee_code` varchar(255) NOT NULL,
    `location` varchar(255) NOT NULL,
    `department` varchar(255) NULL,
    `stock_item` varchar(255) NOT NULL,
    `quantity_ordered` int unsigned NOT NULL,
    `quantity_received` int unsigned NOT NULL,
    `quantity_rejected` int unsigned NOT NULL DEFAULT 0,
    `rejected_file` varchar(100) NULL,
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    
    INDEX `idx_dorgnagainststn_stn` (`stn_number`),
    INDEX `idx_dorgnagainststn_grn` (`grn_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 22. INVENTORY
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_inventory` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `mcc_bmc_user_id` bigint NOT NULL,
    `product_id` bigint NOT NULL,
    `quantity` int unsigned NOT NULL DEFAULT 0,
    
    UNIQUE KEY `unique_user_product` (`mcc_bmc_user_id`, `product_id`),
    FOREIGN KEY (`mcc_bmc_user_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`product_id`) REFERENCES `main_app_product` (`id`) ON DELETE CASCADE,
    INDEX `idx_inventory_user` (`mcc_bmc_user_id`),
    INDEX `idx_inventory_product` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 23. INVENTORY HISTORY
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_inventoryhistory` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `inventory_id` bigint NOT NULL,
    `action` varchar(20) NOT NULL,
    `quantity_change` int NOT NULL,
    `previous_quantity` int unsigned NOT NULL,
    `new_quantity` int unsigned NOT NULL,
    `reference_number` varchar(100) NULL,
    `notes` longtext NULL,
    `performed_by_id` bigint NOT NULL,
    `created_at` datetime(6) NOT NULL,
    
    FOREIGN KEY (`inventory_id`) REFERENCES `main_app_inventory` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`performed_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    INDEX `idx_inventoryhistory_inventory` (`inventory_id`),
    INDEX `idx_inventoryhistory_action` (`action`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 24. MESSAGE QUEUE
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_messagequeue` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `message_type` varchar(20) NOT NULL,
    `advance_sale_id` bigint NULL,
    `unique_code` varchar(50) NOT NULL,
    `mpp_name` varchar(255) NOT NULL,
    `mobile_number` varchar(15) NOT NULL,
    `message` longtext NOT NULL,
    `cycle_info` varchar(100) NULL,
    `status` varchar(20) NOT NULL DEFAULT 'PENDING',
    `retry_count` int NOT NULL DEFAULT 0,
    `max_retries` int NOT NULL DEFAULT 3,
    `created_at` datetime(6) NOT NULL,
    `queued_at` datetime(6) NULL,
    `processing_started_at` datetime(6) NULL,
    `sent_at` datetime(6) NULL,
    `completed_at` datetime(6) NULL,
    `last_error` longtext NULL,
    `error_count` int NOT NULL DEFAULT 0,
    `sequence_number` bigint NOT NULL DEFAULT 0,
    `correlation_id` varchar(100) NULL,
    
    FOREIGN KEY (`advance_sale_id`) REFERENCES `main_app_advancesale` (`id`) ON DELETE CASCADE,
    INDEX `idx_messagequeue_status_created` (`status`, `created_at`),
    INDEX `idx_messagequeue_unique_code` (`unique_code`, `message_type`),
    INDEX `idx_messagequeue_sequence` (`sequence_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 25. ENHANCED MESSAGE QUEUE
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_enhancedmessagequeue` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `message_type` varchar(20) NOT NULL,
    `advance_sale_id` bigint NULL,
    `unique_code` varchar(50) NOT NULL,
    `mpp_name` varchar(255) NOT NULL,
    `mobile_number` varchar(15) NOT NULL,
    `message` longtext NOT NULL,
    `cycle_info` varchar(100) NULL,
    `status` varchar(20) NOT NULL DEFAULT 'PENDING',
    `retry_count` int NOT NULL DEFAULT 0,
    `max_retries` int NOT NULL DEFAULT 3,
    `created_at` datetime(6) NOT NULL,
    `queued_at` datetime(6) NULL,
    `processing_started_at` datetime(6) NULL,
    `sent_at` datetime(6) NULL,
    `completed_at` datetime(6) NULL,
    `last_error` longtext NULL,
    `error_count` int NOT NULL DEFAULT 0,
    `sequence_number` bigint NOT NULL DEFAULT 0,
    `correlation_id` varchar(100) NULL,
    `whatsapp_session_id` varchar(100) NULL,
    `whatsapp_window_active` tinyint(1) NOT NULL DEFAULT 0,
    
    FOREIGN KEY (`advance_sale_id`) REFERENCES `main_app_advancesale` (`id`) ON DELETE CASCADE,
    INDEX `idx_enhancedmessagequeue_status_created` (`status`, `created_at`),
    INDEX `idx_enhancedmessagequeue_unique_code` (`unique_code`, `message_type`),
    INDEX `idx_enhancedmessagequeue_sequence_status` (`sequence_number`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 26. MESSAGE DELIVERY LOG
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_messagedeliverylog` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `message_queue_id` bigint NOT NULL,
    `attempt_number` int NOT NULL,
    `status` varchar(20) NOT NULL,
    `sent_via` varchar(50) NULL,
    `notes` varchar(255) NULL,
    `error_message` longtext NULL,
    `response_time_ms` int NULL,
    `created_at` datetime(6) NOT NULL,
    
    FOREIGN KEY (`message_queue_id`) REFERENCES `main_app_messagequeue` (`id`) ON DELETE CASCADE,
    INDEX `idx_messagedeliverylog_queue` (`message_queue_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 27. WHATSAPP LOG
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_whatsapplog` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `mobile_number` varchar(15) NOT NULL,
    `message` longtext NOT NULL,
    `unique_code` varchar(50) NULL,
    `mpp_name` varchar(255) NULL,
    `status` varchar(20) NOT NULL DEFAULT 'PENDING',
    `sent_via` varchar(20) NOT NULL DEFAULT 'META_API',
    `template_name` varchar(100) NULL,
    `template_message_id` varchar(100) NULL,
    `template_variables` json NULL,
    `api_response` json NULL,
    `error_message` longtext NULL,
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    `sent_at` datetime(6) NULL,
    `delivered_at` datetime(6) NULL,
    `read_at` datetime(6) NULL,
    `is_read` tinyint(1) NOT NULL DEFAULT 0,
    `read_count` int NOT NULL DEFAULT 0,
    `last_read_at` datetime(6) NULL,
    `not_registered` tinyint(1) NOT NULL DEFAULT 0,
    `completed_at` datetime(6) NULL,
    `purpose` varchar(50) NOT NULL DEFAULT 'GENERAL',
    `advance_sale_id` bigint NULL,
    
    FOREIGN KEY (`advance_sale_id`) REFERENCES `main_app_advancesale` (`id`) ON DELETE SET NULL,
    INDEX `idx_whatsapplog_mobile_created` (`mobile_number`, `created_at`),
    INDEX `idx_whatsapplog_status_created` (`status`, `created_at`),
    INDEX `idx_whatsapplog_template_id` (`template_message_id`),
    INDEX `idx_whatsapplog_unique_code` (`unique_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 28. SMS QUEUE
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_smsqueue` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `mobile_number` varchar(15) NOT NULL,
    `unique_code` varchar(50) NOT NULL,
    `mpp_name` varchar(255) NOT NULL,
    `cycle_info` varchar(100) NULL,
    `retry_count` int NOT NULL DEFAULT 0,
    `status` varchar(20) NOT NULL DEFAULT 'PENDING',
    `created_at` datetime(6) NOT NULL,
    `processed_at` datetime(6) NULL,
    `attempts` int NOT NULL DEFAULT 0,
    `last_error` longtext NULL,
    `sent_at` datetime(6) NULL,
    
    INDEX `idx_smsqueue_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 29. RECONCILIATION SHEET
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_reconciliationsheet` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `uploaded_by_id` bigint NOT NULL,
    `file_name` varchar(255) NOT NULL,
    `upload_date` datetime(6) NOT NULL,
    `monthly_cycle_id` bigint NOT NULL,
    `cycle_id` bigint NOT NULL,
    `status` varchar(20) NOT NULL DEFAULT 'UPLOADED',
    `processed_at` datetime(6) NULL,
    `total_records` int unsigned NOT NULL DEFAULT 0,
    `over_recorded_count` int unsigned NOT NULL DEFAULT 0,
    `under_recorded_count` int unsigned NOT NULL DEFAULT 0,
    `perfect_match_count` int unsigned NOT NULL DEFAULT 0,
    `not_recorded_count` int unsigned NOT NULL DEFAULT 0,
    `excel_file` varchar(100) NULL,
    
    FOREIGN KEY (`uploaded_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`monthly_cycle_id`) REFERENCES `main_app_monthlycycle` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`cycle_id`) REFERENCES `main_app_cycle` (`id`) ON DELETE CASCADE,
    INDEX `idx_reconciliationsheet_uploaded_by` (`uploaded_by_id`),
    INDEX `idx_reconciliationsheet_cycle` (`cycle_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 30. RECONCILIATION RECORD
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_reconciliationrecord` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `reconciliation_sheet_id` bigint NOT NULL,
    `location` varchar(255) NOT NULL,
    `mpp_code` varchar(50) NOT NULL,
    `mpp_name` varchar(255) NOT NULL,
    `mpp_id` bigint NULL,
    `product_name` varchar(255) NOT NULL,
    `product_id` bigint NULL,
    `advance_sale_qty` int NOT NULL DEFAULT 0,
    `sap_entry_qty` int NOT NULL,
    `quantity_difference` int NOT NULL DEFAULT 0,
    `status` varchar(20) NOT NULL,
    `match_quality` varchar(100) NOT NULL,
    `to_be_sent_to_mpp` int NOT NULL DEFAULT 0,
    `to_be_deducted` int NOT NULL DEFAULT 0,
    `is_service` tinyint(1) NOT NULL DEFAULT 0,
    `is_processed` tinyint(1) NOT NULL DEFAULT 0,
    `processed_at` datetime(6) NULL,
    `is_acknowledged` tinyint(1) NOT NULL DEFAULT 0,
    `acknowledged_at` datetime(6) NULL,
    `acknowledged_by_id` bigint NULL,
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    
    UNIQUE KEY `unique_sheet_location_mpp_product` (`reconciliation_sheet_id`, `location`, `mpp_code`, `product_name`),
    FOREIGN KEY (`reconciliation_sheet_id`) REFERENCES `main_app_reconciliationsheet` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`mpp_id`) REFERENCES `main_app_mppwithcode` (`id`) ON DELETE SET NULL,
    FOREIGN KEY (`product_id`) REFERENCES `main_app_product` (`id`) ON DELETE SET NULL,
    FOREIGN KEY (`acknowledged_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE SET NULL,
    INDEX `idx_reconciliationrecord_sheet` (`reconciliation_sheet_id`),
    INDEX `idx_reconciliationrecord_mpp` (`mpp_id`),
    INDEX `idx_reconciliationrecord_product` (`product_id`),
    INDEX `idx_reconciliationrecord_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 31. MPP PRODUCT LEDGER
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_mppproductledger` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `mpp_id` bigint NOT NULL,
    `product_id` bigint NOT NULL,
    `cycle_id` bigint NOT NULL,
    `opening_balance` int NOT NULL DEFAULT 0,
    `current_advance_sale` int NOT NULL DEFAULT 0,
    `current_sap_entry` int NOT NULL DEFAULT 0,
    `current_difference` int NOT NULL DEFAULT 0,
    `closing_balance` int NOT NULL DEFAULT 0,
    `is_reconciled` tinyint(1) NOT NULL DEFAULT 0,
    `reconciled_at` datetime(6) NULL,
    `reconciliation_record_id` bigint NULL,
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    
    UNIQUE KEY `unique_mpp_product_cycle` (`mpp_id`, `product_id`, `cycle_id`),
    FOREIGN KEY (`mpp_id`) REFERENCES `main_app_mppwithcode` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`product_id`) REFERENCES `main_app_product` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`cycle_id`) REFERENCES `main_app_cycle` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`reconciliation_record_id`) REFERENCES `main_app_reconciliationrecord` (`id`) ON DELETE SET NULL,
    INDEX `idx_mppproductledger_mpp` (`mpp_id`),
    INDEX `idx_mppproductledger_product` (`product_id`),
    INDEX `idx_mppproductledger_cycle` (`cycle_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 32. CYCLE PRODUCT SUMMARY
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_cycleproductsummary` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `cycle_id` bigint NOT NULL,
    `product_id` bigint NOT NULL,
    `total_advance_sale` int NOT NULL DEFAULT 0,
    `total_sap_entry` int NOT NULL DEFAULT 0,
    `total_difference` int NOT NULL DEFAULT 0,
    `total_to_send` int NOT NULL DEFAULT 0,
    `total_to_deduct` int NOT NULL DEFAULT 0,
    `mpp_count` int NOT NULL DEFAULT 0,
    `reconciled_count` int NOT NULL DEFAULT 0,
    
    UNIQUE KEY `unique_cycle_product` (`cycle_id`, `product_id`),
    FOREIGN KEY (`cycle_id`) REFERENCES `main_app_cycle` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`product_id`) REFERENCES `main_app_product` (`id`) ON DELETE CASCADE,
    INDEX `idx_cycleproductsummary_cycle` (`cycle_id`),
    INDEX `idx_cycleproductsummary_product` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 33. CYCLE LEDGER
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_cycleledger` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `cycle_id` bigint NOT NULL,
    `product_id` bigint NOT NULL,
    `opening_balance` int NOT NULL DEFAULT 0,
    `advance_sale_qty` int NOT NULL DEFAULT 0,
    `sap_entry_qty` int NOT NULL DEFAULT 0,
    `closing_balance` int NOT NULL DEFAULT 0,
    `is_reconciled` tinyint(1) NOT NULL DEFAULT 0,
    `reconciliation_date` datetime(6) NULL,
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    
    UNIQUE KEY `unique_cycle_product_ledger` (`cycle_id`, `product_id`),
    FOREIGN KEY (`cycle_id`) REFERENCES `main_app_cycle` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`product_id`) REFERENCES `main_app_product` (`id`) ON DELETE CASCADE,
    INDEX `idx_cycleledger_cycle` (`cycle_id`),
    INDEX `idx_cycleledger_product` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 34. GENERAL SALE
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_generalsale` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `reconciliation_record_id` bigint NULL,
    `location` varchar(255) NOT NULL,
    `mpp_id` bigint NOT NULL,
    `product_id` bigint NOT NULL,
    `quantity` int unsigned NOT NULL,
    `cycle_id` bigint NOT NULL,
    `status` varchar(20) NOT NULL DEFAULT 'PENDING',
    `dispatched_at` datetime(6) NULL,
    `delivered_at` datetime(6) NULL,
    `pdf_file` varchar(100) NULL,
    `whatsapp_sent` tinyint(1) NOT NULL DEFAULT 0,
    `whatsapp_sent_at` datetime(6) NULL,
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    
    FOREIGN KEY (`reconciliation_record_id`) REFERENCES `main_app_reconciliationrecord` (`id`) ON DELETE SET NULL,
    FOREIGN KEY (`mpp_id`) REFERENCES `main_app_mppwithcode` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`product_id`) REFERENCES `main_app_product` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`cycle_id`) REFERENCES `main_app_cycle` (`id`) ON DELETE CASCADE,
    INDEX `idx_generalsale_mpp` (`mpp_id`),
    INDEX `idx_generalsale_product` (`product_id`),
    INDEX `idx_generalsale_cycle` (`cycle_id`),
    INDEX `idx_generalsale_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 35. RECONCILIATION NOTIFICATION
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_reconciliationnotification` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `reconciliation_sheet_id` bigint NOT NULL,
    `location_user_id` bigint NOT NULL,
    `location` varchar(255) NOT NULL,
    `status` varchar(20) NOT NULL DEFAULT 'PENDING',
    `sent_at` datetime(6) NULL,
    `viewed_at` datetime(6) NULL,
    `acknowledged_at` datetime(6) NULL,
    `message` longtext NOT NULL,
    `pdf_file` varchar(100) NULL,
    `user_comments` longtext NULL,
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    
    UNIQUE KEY `unique_sheet_user` (`reconciliation_sheet_id`, `location_user_id`),
    FOREIGN KEY (`reconciliation_sheet_id`) REFERENCES `main_app_reconciliationsheet` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`location_user_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    INDEX `idx_reconciliationnotification_sheet` (`reconciliation_sheet_id`),
    INDEX `idx_reconciliationnotification_user` (`location_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 36. SAP PO EXCEL UPLOAD
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_sappoexcelupload` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `uploaded_by_id` bigint NOT NULL,
    `filename` varchar(255) NOT NULL,
    `upload_date` datetime(6) NOT NULL,
    `total_rows` int unsigned NOT NULL DEFAULT 0,
    `rows_processed` int unsigned NOT NULL DEFAULT 0,
    `rows_succeeded` int unsigned NOT NULL DEFAULT 0,
    `rows_failed` int unsigned NOT NULL DEFAULT 0,
    `status` varchar(20) NOT NULL DEFAULT 'PENDING',
    
    FOREIGN KEY (`uploaded_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    INDEX `idx_sappoexcelupload_uploaded_by` (`uploaded_by_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 37. SAP MATERIAL PO MAPPING
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_sapmaterialpomapping` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `upload_id` bigint NOT NULL,
    `product_group_id` bigint NULL,
    `sap_material_code` varchar(100) NOT NULL,
    `sap_material_name` varchar(500) NOT NULL,
    `po_number` varchar(50) NOT NULL,
    `order_quantity` decimal(15,2) NOT NULL,
    `plant` varchar(100) NULL,
    `storage_location` varchar(100) NULL,
    `document_date` date NOT NULL,
    `vendor_info` varchar(500) NULL,
    `is_used` tinyint(1) NOT NULL DEFAULT 0,
    `used_in_requisition_id` bigint NULL,
    `used_by_id` bigint NULL,
    `used_at` datetime(6) NULL,
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    
    UNIQUE KEY `unique_po_material` (`po_number`, `sap_material_code`),
    FOREIGN KEY (`upload_id`) REFERENCES `main_app_sappoexcelupload` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`product_group_id`) REFERENCES `main_app_productmappinggroup` (`id`) ON DELETE SET NULL,
    FOREIGN KEY (`used_in_requisition_id`) REFERENCES `main_app_purchaserequisition` (`id`) ON DELETE SET NULL,
    FOREIGN KEY (`used_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE SET NULL,
    INDEX `idx_sapmaterialpomapping_po_used` (`po_number`, `is_used`),
    INDEX `idx_sapmaterialpomapping_group_used` (`product_group_id`, `is_used`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 38. UPLOAD BATCH
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_uploadbatch` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `batch_id` varchar(100) NOT NULL UNIQUE,
    `file_name` varchar(255) NOT NULL,
    `file_size` int unsigned NOT NULL,
    `uploaded_by_id` bigint NULL,
    `uploaded_at` datetime(6) NOT NULL,
    `processing_started_at` datetime(6) NULL,
    `processing_completed_at` datetime(6) NULL,
    `status` varchar(50) NOT NULL DEFAULT 'PENDING',
    `total_rows` int unsigned NOT NULL DEFAULT 0,
    `rows_processed` int unsigned NOT NULL DEFAULT 0,
    `rows_succeeded` int unsigned NOT NULL DEFAULT 0,
    `rows_failed` int unsigned NOT NULL DEFAULT 0,
    `error_summary` json NULL,
    `metrics` json NULL,
    
    FOREIGN KEY (`uploaded_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE SET NULL,
    INDEX `idx_uploadbatch_batch_id` (`batch_id`),
    INDEX `idx_uploadbatch_status_created` (`status`, `uploaded_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 39. PROCESSING ERROR LOG
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_processingerrorlog` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `batch_id` bigint NOT NULL,
    `row_index` int unsigned NOT NULL,
    `field` varchar(100) NULL,
    `value` longtext NULL,
    `rule` varchar(100) NOT NULL,
    `error_message` longtext NOT NULL,
    `suggestion` longtext NULL,
    `is_critical` tinyint(1) NOT NULL DEFAULT 1,
    `created_at` datetime(6) NOT NULL,
    
    FOREIGN KEY (`batch_id`) REFERENCES `main_app_uploadbatch` (`id`) ON DELETE CASCADE,
    INDEX `idx_processingerrorlog_batch_row` (`batch_id`, `row_index`),
    INDEX `idx_processingerrorlog_rule` (`rule`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 40. PRODUCT MAPPING UPLOAD
-- ============================================
CREATE TABLE IF NOT EXISTS `product_mapping_uploads` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `upload_id` varchar(100) NOT NULL UNIQUE,
    `user_id` int NULL,
    `filename` varchar(255) NOT NULL,
    `file_size` int NOT NULL,
    `status` varchar(50) NOT NULL,
    `progress` float NOT NULL DEFAULT 0,
    `metrics` json NOT NULL,
    `error_message` longtext NULL,
    `started_at` datetime(6) NOT NULL,
    `completed_at` datetime(6) NULL,
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    
    INDEX `idx_productmappinguploads_status_created` (`status`, `created_at`),
    INDEX `idx_productmappinguploads_user_created` (`user_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 41. RECONCILIATION AUDIT LOG
-- ============================================
CREATE TABLE IF NOT EXISTS `reconciliation_audit_logs` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `upload_id` bigint NOT NULL,
    `row_index` int NOT NULL,
    `action_type` varchar(50) NOT NULL,
    `entity_type` varchar(50) NOT NULL,
    `entity_id` int NULL,
    `entity_identifier` varchar(500) NOT NULL,
    `changes` json NOT NULL,
    `error_details` json NOT NULL,
    `timestamp` datetime(6) NOT NULL,
    
    FOREIGN KEY (`upload_id`) REFERENCES `product_mapping_uploads` (`id`) ON DELETE CASCADE,
    INDEX `idx_reconciliationauditlogs_upload_row` (`upload_id`, `row_index`),
    INDEX `idx_reconciliationauditlogs_action_timestamp` (`action_type`, `timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 42. EMAIL SETTINGS
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_emailsettings` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `subject` varchar(255) NOT NULL DEFAULT 'Purchase Requisition Notification',
    `from_email` varchar(254) NOT NULL DEFAULT 'shivamc36@gmail.com',
    `cc_emails` longtext NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 43. EMPLOYEE
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_employee` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `employee_code` varchar(100) NOT NULL UNIQUE,
    `employee_name` varchar(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 44. MESSAGE
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_message` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `user_id` bigint NOT NULL,
    `recipient` varchar(100) NOT NULL,
    `content` longtext NOT NULL,
    `created_at` datetime(6) NOT NULL,
    
    FOREIGN KEY (`user_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    INDEX `idx_message_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 45. MCC BMC USER
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_mccbmcuser` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `user_id` bigint NOT NULL,
    `location` varchar(255) NOT NULL,
    
    FOREIGN KEY (`user_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    INDEX `idx_mccbmcuser_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 46. TRANSFER
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_transfer` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `from_user_id` bigint NOT NULL,
    `to_user_id` bigint NOT NULL,
    `product_id` bigint NOT NULL,
    `quantity` int unsigned NOT NULL,
    `created_at` datetime(6) NOT NULL,
    `status` varchar(10) NOT NULL DEFAULT 'PENDING',
    
    FOREIGN KEY (`from_user_id`) REFERENCES `main_app_mccbmcuser` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`to_user_id`) REFERENCES `main_app_mccbmcuser` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`product_id`) REFERENCES `main_app_product` (`id`) ON DELETE CASCADE,
    INDEX `idx_transfer_from_user` (`from_user_id`),
    INDEX `idx_transfer_to_user` (`to_user_id`),
    INDEX `idx_transfer_product` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 47. DISPATCH NOTIFICATION
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_disp

atchnotification` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `logistic_department_id` bigint NOT NULL,
    `from_user_id` bigint NOT NULL,
    `to_user_id` bigint NOT NULL,
    `is_dispatched` tinyint(1) NOT NULL DEFAULT 0,
    `created_at` datetime(6) NOT NULL,
    
    FOREIGN KEY (`logistic_department_id`) REFERENCES `main_app_logisticdepartment` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`from_user_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`to_user_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    INDEX `idx_dispnotif_logistic` (`logistic_department_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 48. DISPATCH LOG
-- ============================================
CREATE TABLE IF NOT EXISTS `main_app_dispatchlog` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `logistic_department_id` bigint NOT NULL,
    `dispatched_by_id` bigint NOT NULL,
    `quantity` int unsigned NOT NULL,
    `dispatched_at` datetime(6) NOT NULL,
    
    FOREIGN KEY (`logistic_department_id`) REFERENCES `main_app_logisticdepartment` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`dispatched_by_id`) REFERENCES `main_app_customuser` (`id`) ON DELETE CASCADE,
    INDEX `idx_dispatchlog_logistic` (`logistic_department_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
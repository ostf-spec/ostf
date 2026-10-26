# SPDX-License-Identifier: Apache-2.0
# The shop's database: one PostgreSQL instance with daily snapshots.

resource "aws_kms_key" "database" {
  description             = "Encrypts the shop database and its snapshots"
  enable_key_rotation     = true
  rotation_period_in_days = 365
}

resource "aws_db_instance" "shop" {
  identifier                  = "shop"
  engine                      = "postgres"
  engine_version              = "17"
  instance_class              = "db.t4g.medium"
  allocated_storage           = 50
  storage_encrypted           = true
  kms_key_id                  = aws_kms_key.database.arn
  backup_retention_period     = 14
  copy_tags_to_snapshot       = true
  deletion_protection         = true
  username                    = "shop"
  manage_master_user_password = true
}

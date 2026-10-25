# SPDX-License-Identifier: Apache-2.0

# The payments database. trace.yaml links this whole file to R-DATA-AT-REST:
# no language annex covers Terraform, so the anchor is the path alone and the
# lock records an lf1 fingerprint of the file's bytes (OSTF-141). A tag comment
# in this file would not be read (OSTF-133).
resource "aws_db_instance" "payments" {
  identifier        = "payments"
  engine            = "postgres"
  storage_encrypted = true
  kms_key_id        = aws_kms_key.payments.arn
}

resource "aws_kms_key" "payments" {
  description         = "Payments database at rest"
  enable_key_rotation = true
}

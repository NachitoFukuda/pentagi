package main

import (
	"context"
	"database/sql"
	"fmt"
	"golang.org/x/crypto/bcrypt"
)

// Replace only the known upstream seed password, before opening the listener.
// Restarts must never overwrite an administrator's chosen password.
func bootstrapAdmin(ctx context.Context, db *sql.DB, password string) error {
	if password == "" {
		return nil
	}
	if len(password) < 20 || len(password) > 72 {
		return fmt.Errorf("bootstrap password must contain 20 to 72 bytes")
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return fmt.Errorf("cannot hash bootstrap password")
	}
	_, err = db.ExecContext(ctx, `UPDATE users SET password=$1, password_change_required=false
		WHERE mail='admin@pentagi.com' AND password=$2 AND password_change_required=true`,
		string(hash), "$2a$10$deVOk0o1nYRHpaVXjIcyCuRmaHvtoMN/2RUT7w5XbZTeiWKEbXx9q")
	return err
}

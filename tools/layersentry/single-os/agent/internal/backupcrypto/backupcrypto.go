package backupcrypto

import (
    "crypto/sha256"
    "encoding/hex"
    "errors"
    "fmt"
    "io"
    "os"
    "path/filepath"
    "strings"

    "filippo.io/age"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
)

const maxRetainedIdentities = 4

type Keyring struct {
    path       string
    active     *age.X25519Identity
    identities []age.Identity
}

type Digest struct {
    SHA256    string
    SizeBytes int64
}

func Open(path string) (*Keyring, error) {
    if !filepath.IsAbs(path) {
        return nil, errors.New("backup key path must be absolute")
    }
    if err := privateDir(filepath.Dir(path)); err != nil {
        return nil, err
    }
    if _, err := os.Lstat(path); errors.Is(err, os.ErrNotExist) {
        id, err := age.GenerateX25519Identity()
        if err != nil {
            return nil, err
        }
        if err = createExclusiveKey(path, id.String()+"\n"); err != nil {
            return nil, err
        }
    } else if err != nil {
        return nil, err
    }
    return load(path)
}

func load(path string) (*Keyring, error) {
    fi, err := os.Lstat(path)
    if err != nil {
        return nil, err
    }
    if fi.Mode()&os.ModeSymlink != 0 || !fi.Mode().IsRegular() || fi.Mode().Perm()&0077 != 0 || fi.Size() < 32 || fi.Size() > 32<<10 {
        return nil, errors.New("unsafe backup keyring")
    }
    raw, err := os.ReadFile(path)
    if err != nil {
        return nil, err
    }
    lines := strings.Split(strings.TrimSpace(string(raw)), "\n")
    if len(lines) == 0 || len(lines) > maxRetainedIdentities {
        return nil, errors.New("backup keyring identity count invalid")
    }
    identities := make([]age.Identity, 0, len(lines))
    var active *age.X25519Identity
    for i, line := range lines {
        line = strings.TrimSpace(line)
        id, err := age.ParseX25519Identity(line)
        if err != nil {
            return nil, errors.New("backup keyring contains a non-X25519 or malformed identity")
        }
        if i == 0 {
            active = id
        }
        identities = append(identities, id)
    }
    return &Keyring{path: path, active: active, identities: identities}, nil
}

// Rotate prepends a new active identity while retaining a bounded number of old
// identities so existing backups remain decryptable. Rotation is intentionally
// a server-side lifecycle primitive; no browser endpoint is exposed here.
func (k *Keyring) Rotate() error {
    if k == nil || k.active == nil {
        return errors.New("backup keyring unavailable")
    }
    id, err := age.GenerateX25519Identity()
    if err != nil {
        return err
    }
    lines := []string{id.String()}
    for _, old := range k.identities {
        x, ok := old.(*age.X25519Identity)
        if !ok {
            return errors.New("backup keyring contains unsupported identity type")
        }
        if len(lines) >= maxRetainedIdentities {
            break
        }
        lines = append(lines, x.String())
    }
    if err = filesystem.AtomicWrite(k.path, []byte(strings.Join(lines, "\n")+"\n"), 0600, filepath.Dir(k.path)); err != nil {
        return err
    }
    refreshed, err := load(k.path)
    if err != nil {
        return err
    }
    *k = *refreshed
    return nil
}

func (k *Keyring) ActiveKeyID() string {
    if k == nil || k.active == nil {
        return ""
    }
    sum := sha256.Sum256([]byte(k.active.Recipient().String()))
    return hex.EncodeToString(sum[:])
}

func (k *Keyring) EncryptFile(src, srcRoot, dst, dstRoot string) (Digest, error) {
    if k == nil || k.active == nil {
        return Digest{}, errors.New("backup encryption keyring unavailable")
    }
    if err := safeRegularWithin(src, srcRoot); err != nil {
        return Digest{}, fmt.Errorf("backup plaintext source rejected: %w", err)
    }
    if err := safeNewPathWithin(dst, dstRoot); err != nil {
        return Digest{}, fmt.Errorf("backup encrypted destination rejected: %w", err)
    }
    if err := os.MkdirAll(filepath.Dir(dst), 0700); err != nil {
        return Digest{}, err
    }

    in, err := os.Open(src)
    if err != nil {
        return Digest{}, err
    }
    defer in.Close()

    out, err := os.OpenFile(dst, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
    if err != nil {
        return Digest{}, err
    }
    ok := false
    defer func() {
        _ = out.Close()
        if !ok {
            _ = os.Remove(dst)
        }
    }()

    encrypted, err := age.Encrypt(out, k.active.Recipient())
    if err != nil {
        return Digest{}, err
    }
    if _, err = io.Copy(encrypted, in); err != nil {
        _ = encrypted.Close()
        return Digest{}, err
    }
    if err = encrypted.Close(); err != nil {
        return Digest{}, err
    }
    if err = out.Sync(); err != nil {
        return Digest{}, err
    }
    if err = out.Close(); err != nil {
        return Digest{}, err
    }
    if err = fsyncDir(filepath.Dir(dst)); err != nil {
        return Digest{}, err
    }
    ok = true
    return inspect(dst)
}

func (k *Keyring) DecryptFile(src, srcRoot, dst, dstRoot string) error {
    if k == nil || len(k.identities) == 0 {
        return errors.New("backup decryption keyring unavailable")
    }
    if err := safeRegularWithin(src, srcRoot); err != nil {
        return fmt.Errorf("backup ciphertext source rejected: %w", err)
    }
    if err := safeNewPathWithin(dst, dstRoot); err != nil {
        return fmt.Errorf("backup restore destination rejected: %w", err)
    }
    if err := os.MkdirAll(filepath.Dir(dst), 0700); err != nil {
        return err
    }

    in, err := os.Open(src)
    if err != nil {
        return err
    }
    defer in.Close()
    plaintext, err := age.Decrypt(in, k.identities...)
    if err != nil {
        return err
    }
    out, err := os.OpenFile(dst, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
    if err != nil {
        return err
    }
    ok := false
    defer func() {
        _ = out.Close()
        if !ok {
            _ = os.Remove(dst)
        }
    }()
    if _, err = io.Copy(out, plaintext); err != nil {
        return err
    }
    if err = out.Sync(); err != nil {
        return err
    }
    if err = out.Close(); err != nil {
        return err
    }
    ok = true
    return nil
}

func VerifyCiphertext(path, root, expectedSHA string, expectedSize int64) error {
    if err := safeRegularWithin(path, root); err != nil {
        return err
    }
    d, err := inspect(path)
    if err != nil {
        return err
    }
    if d.SHA256 != expectedSHA || d.SizeBytes != expectedSize {
        return errors.New("encrypted backup checksum/size verification failed")
    }
    return nil
}

func inspect(path string) (Digest, error) {
    f, err := os.Open(path)
    if err != nil {
        return Digest{}, err
    }
    defer f.Close()
    st, err := f.Stat()
    if err != nil {
        return Digest{}, err
    }
    if !st.Mode().IsRegular() || st.Size() < 64 {
        return Digest{}, errors.New("encrypted backup is empty or unsafe")
    }
    h := sha256.New()
    if _, err = io.Copy(h, f); err != nil {
        return Digest{}, err
    }
    return Digest{SHA256: hex.EncodeToString(h.Sum(nil)), SizeBytes: st.Size()}, nil
}

func safeRegularWithin(path, root string) error {
    if err := confined(path, root); err != nil {
        return err
    }
    fi, err := os.Lstat(path)
    if err != nil {
        return err
    }
    if fi.Mode()&os.ModeSymlink != 0 || !fi.Mode().IsRegular() {
        return errors.New("path is not a safe regular file")
    }
    return nil
}

func safeNewPathWithin(path, root string) error {
    if err := confined(path, root); err != nil {
        return err
    }
    if _, err := os.Lstat(path); err == nil {
        return errors.New("destination already exists")
    } else if !errors.Is(err, os.ErrNotExist) {
        return err
    }
    return nil
}

func confined(path, root string) error {
    if !filepath.IsAbs(path) || !filepath.IsAbs(root) || filepath.Clean(path) != path || filepath.Clean(root) != root {
        return errors.New("paths must be clean and absolute")
    }
    rel, err := filepath.Rel(root, path)
    if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
        return errors.New("path is outside allowed root")
    }
    return nil
}

func privateDir(path string) error {
    if err := os.MkdirAll(path, 0700); err != nil {
        return err
    }
    fi, err := os.Lstat(path)
    if err != nil {
        return err
    }
    if !fi.IsDir() || fi.Mode()&os.ModeSymlink != 0 || fi.Mode().Perm()&0022 != 0 {
        return errors.New("backup key directory must be private and non-symlink")
    }
    return nil
}

func createExclusiveKey(path, value string) error {
    f, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
    if err != nil {
        return err
    }
    ok := false
    defer func() {
        _ = f.Close()
        if !ok {
            _ = os.Remove(path)
        }
    }()
    if _, err = io.WriteString(f, value); err != nil {
        return err
    }
    if err = f.Sync(); err != nil {
        return err
    }
    if err = f.Close(); err != nil {
        return err
    }
    if err = fsyncDir(filepath.Dir(path)); err != nil {
        return err
    }
    ok = true
    return nil
}

func fsyncDir(path string) error {
    d, err := os.Open(path)
    if err != nil {
        return err
    }
    defer d.Close()
    return d.Sync()
}

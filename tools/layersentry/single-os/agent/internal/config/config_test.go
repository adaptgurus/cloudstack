package config

import (
    "strings"
    "testing"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

func validRequest() model.ServiceRequest {
    return model.ServiceRequest{
        SchemaVersion: 1,
        RequestID: "11111111-1111-4111-8111-111111111111",
        ServiceID: "22222222-2222-4222-8222-222222222222",
        OperationID: "33333333-3333-4333-8333-333333333333",
        IdempotencyKey: "44444444-4444-4444-8444-444444444444",
        Category: model.CategoryDatabase,
        Provider: "postgresql",
        ReleaseLine: "17",
        Topology: "standalone",
        Network: model.NetworkSpec{ListenAddress:"127.0.0.1",Port:5432,AllowedCIDRs:[]string{"10.20.0.0/16"}},
        Maintenance: model.MaintenancePolicy{Mode:"manual",ReleaseLineLocked:true},
        Backup: model.BackupPolicy{Enabled:true,Schedule:"daily",Retention:7},
        SecretRefs: map[string]string{"admin_password":"secret://55555555-5555-4555-8555-555555555555"},
    }
}

func TestValidateAcceptsMinimumStandalone(t *testing.T){if err:=Validate(validRequest());err!=nil{t.Fatalf("valid request rejected: %v",err)}}
func TestValidateRejectsUnknownSchema(t *testing.T){r:=validRequest();r.SchemaVersion=2;if err:=Validate(r);err==nil{t.Fatal("expected schema rejection")}}
func TestDecodeStrictRejectsUnknownField(t *testing.T){data:=`{"schema_version":1,"request_id":"11111111-1111-4111-8111-111111111111","service_id":"22222222-2222-4222-8222-222222222222","operation_id":"33333333-3333-4333-8333-333333333333","idempotency_key":"44444444-4444-4444-8444-444444444444","category":"database","provider":"postgresql","release_line":"17","topology":"standalone","network":{"listen_address":"127.0.0.1","port":5432,"allowed_cidrs":["10.0.0.0/8"]},"maintenance":{"mode":"manual","auto_patch":false,"release_line_locked":true},"backup":{"enabled":false},"secret_refs":{"admin_password":"secret://55555555-5555-4555-8555-555555555555"},"unexpected":true}`;if _,err:=DecodeStrict([]byte(data));err==nil{t.Fatal("expected unknown-field rejection")}}
func TestValidateRejectsNonUUIDOperation(t *testing.T){r:=validRequest();r.OperationID="../op";if err:=Validate(r);err==nil{t.Fatal("expected UUID rejection")}}
func TestValidateRejectsPlaintextSecret(t *testing.T){r:=validRequest();r.SecretRefs["admin_password"]="plaintext";if err:=Validate(r);err==nil{t.Fatal("expected secret reference rejection")}}
func TestValidateRejectsDuplicateDisk(t *testing.T){r:=validRequest();r.Storage=[]model.StorageAssignment{{Device:"/dev/disk/by-id/wwn-a",MountPoint:"/data/a",Purpose:"database-data",Filesystem:"xfs"},{Device:"/dev/disk/by-id/wwn-a",MountPoint:"/data/b",Purpose:"database-wal",Filesystem:"xfs"}};if err:=Validate(r);err==nil{t.Fatal("expected duplicate disk rejection")}}
func TestValidateRejectsUnsafeMount(t *testing.T){r:=validRequest();r.Storage=[]model.StorageAssignment{{Device:"/dev/disk/by-id/wwn-a",MountPoint:"/etc",Purpose:"database-data",Filesystem:"xfs"}};if err:=Validate(r);err==nil{t.Fatal("expected unsafe mount rejection")}}
func TestValidateRequiresFormatConfirmation(t *testing.T){r:=validRequest();r.Storage=[]model.StorageAssignment{{Device:"/dev/disk/by-id/wwn-a",MountPoint:"/data/db",Purpose:"database-data",Filesystem:"xfs",Format:true}};if err:=Validate(r);err==nil{t.Fatal("expected format confirmation rejection")}}
func TestValidateRejectsInvalidCIDR(t *testing.T){r:=validRequest();r.Network.AllowedCIDRs=[]string{"10.0.0.1/99"};if err:=Validate(r);err==nil{t.Fatal("expected CIDR rejection")}}
func TestValidateRejectsStandaloneClusterFields(t *testing.T){r:=validRequest();r.Cluster.Role="primary";if err:=Validate(r);err==nil{t.Fatal("expected standalone cluster field rejection")}}
func TestValidateRejectsDuplicateClusterPeers(t *testing.T){r:=validRequest();r.Topology="cluster";r.Cluster=model.ClusterSpec{Role:"primary",Peers:[]string{"10.0.0.2","10.0.0.2"},JoinTokenRef:"secret://66666666-6666-4666-8666-666666666666"};if err:=Validate(r);err==nil{t.Fatal("expected duplicate peer rejection")}}
func TestCanonicalDigestChangesWithSecretReference(t *testing.T){a:=validRequest();b:=validRequest();b.SecretRefs["admin_password"]="secret://77777777-7777-4777-8777-777777777777";da,_:=CanonicalDigest(a);db,_:=CanonicalDigest(b);if da==db{t.Fatal("digest must bind secret reference identity")}}
func TestDecodeStrictRejectsTrailingDocument(t *testing.T){r:=validRequest();_ = r;data:=`{"schema_version":1} {"schema_version":1}`;if _,err:=DecodeStrict([]byte(data));err==nil||!strings.Contains(err.Error(),"decode"){t.Fatalf("expected strict decode failure, got %v",err)}}

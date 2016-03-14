angular.module('settingsPage', [
    'ngRoute'
])



    .config(function($routeProvider) {
        $routeProvider.when('/me/settings', {
            templateUrl: 'settings-page/settings-page.tpl.html',
            controller: 'settingsPageCtrl',
            resolve: {
                isAuth: function($q, $auth){
                    if ($auth.isAuthenticated()){
                        return $q.resolve()
                    }
                    else {
                        return $q.reject("/settings only works if you're logged in.")
                    }
                }
            }
        })
    })



    .controller("settingsPageCtrl", function($scope, $auth, $location, $http){

        console.log("the settings page loaded")
        $scope.wantToDelete = false
        $scope.deleteProfile = function() {
            $http.delete("/api/me")
                .success(function(resp){
                    $auth.logout()
                    $location.path("/")
                    alert("Your profile has been deleted.")
                })
                .error(function(){
                    alert("Sorry, something went wrong!")
                })
        }


        $scope.syncState = 'ready'

        $scope.pullFromOrcid = function(){
            console.log("ah, refreshing!")
            $scope.syncState = "working"
            $http.post("/api/me", {action: "pull_from_orcid"})
                .success(function(resp){
                    console.log("we updated you successfully!")
                    $scope.syncState = "success"
                })
        }

    })













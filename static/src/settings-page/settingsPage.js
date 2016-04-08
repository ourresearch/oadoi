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



    .controller("settingsPageCtrl", function($scope, $auth, $route, $location, $http, Person){

        console.log("the settings page loaded")
        $scope.orcidId = $auth.getPayload()["sub"]
        $scope.givenNames = $auth.getPayload()["given_names"]

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
                    // force a reload of the person
                    Person.load($auth.getPayload().sub, true).then(
                        function(resp){
                            $scope.syncState = "success"
                            console.log("we reloaded the Person after sync")
                        }
                    )
                })
        }

    })













angular.module('profilePage', [
    'ngRoute',
    'profileService'
  ])



  .config(function($routeProvider) {
    $routeProvider.when('/p/:orcid', {
      templateUrl: 'profile-page/profile-page.tpl.html',
      controller: 'profilePageCtrl',
      resolve: {
        profileResp: function($http, $route){
            console.log("loaded the profile response in the route def")
          var url = "/api/profile/" + $route.current.params.orcid
          return $http.get(url)
        }
      }
    })
  })



  .controller("profilePageCtrl", function($scope,
                                          $routeParams,
                                          ngProgress,
                                          profileResp){
    ngProgress.complete()
    $scope.profile = profileResp.data
    console.log("retrieved the profile", $scope.profile)






  })



